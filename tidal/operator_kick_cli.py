"""API-backed kick commands."""

from __future__ import annotations

from dataclasses import asdict

import typer

from tidal.cli_context import CLIContext, normalize_cli_address
from tidal.cli_options import (
    AccountOption,
    ApiBaseUrlOption,
    ApiTokenOption,
    AuctionAddressOption,
    BroadcastOption,
    BypassConfirmationOption,
    ConfigOption,
    JsonOption,
    KeystoreOption,
    LimitOption,
    PasswordFileOption,
    SenderOption,
    SourceAddressOption,
    SourceTypeOption,
    VerboseOption,
)
from tidal.cli_renderers import emit_json, render_kick_inspect
from tidal.control_plane.client import ControlPlaneError
from tidal.operator_cli_support import (
    execute_prepared_action_sync,
    render_action_preview,
    render_broadcast_result,
    render_warnings,
)
from tidal.ops.kick_inspect import KickInspectEntry, KickInspectResult

app = typer.Typer(help="Kick auction lots", no_args_is_help=True)


def _normalize_source_type_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower().replace("-", "_")
    if normalized in {"strategy", "fee_burner"}:
        return normalized
    raise typer.BadParameter("expected 'strategy' or 'fee-burner'", param_hint="--source-type")


def _inspect_result_from_api(data: dict[str, object]) -> KickInspectResult:
    return KickInspectResult(
        source_type=data["source_type"],
        source_address=data["source_address"],
        auction_address=data["auction_address"],
        limit=data["limit"],
        eligible_count=data["eligible_count"],
        selected_count=data["selected_count"],
        ready_count=data["ready_count"],
        cooldown_count=data["cooldown_count"],
        deferred_same_auction_count=data["deferred_same_auction_count"],
        limited_count=data["limited_count"],
        ready=[KickInspectEntry(**entry) for entry in data["ready"]],
        cooldown_skips=[KickInspectEntry(**entry) for entry in data["cooldown_skips"]],
        deferred_same_auction=[KickInspectEntry(**entry) for entry in data["deferred_same_auction"]],
        limited=[KickInspectEntry(**entry) for entry in data["limited"]],
    )


@app.command("inspect")
def kick_inspect(
    config: ConfigOption = None,
    api_base_url: ApiBaseUrlOption = None,
    api_token: ApiTokenOption = None,
    json_output: JsonOption = False,
    source_type: SourceTypeOption = None,
    source_address: SourceAddressOption = None,
    auction_address: AuctionAddressOption = None,
    limit: LimitOption = None,
    show_all: bool = typer.Option(False, "--show-all", help="Show deferred and limited candidates."),
) -> None:
    cli_ctx = CLIContext(config, api_base_url=api_base_url, api_token=api_token)
    payload = {
        "sourceType": _normalize_source_type_filter(source_type),
        "sourceAddress": normalize_cli_address(source_address, param_hint="--source"),
        "auctionAddress": normalize_cli_address(auction_address, param_hint="--auction"),
        "limit": limit,
    }
    try:
        with cli_ctx.control_plane_client() as client:
            response = client.inspect_kicks(payload)
    except ControlPlaneError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    data = response["data"]
    if json_output:
        emit_json("kick.inspect", status=response["status"], data=data, warnings=response.get("warnings"))
    else:
        render_kick_inspect(_inspect_result_from_api(data), show_all=show_all)
    raise typer.Exit(code=0 if response["status"] == "ok" else 2)


@app.command("run")
def kick_run(
    config: ConfigOption = None,
    api_base_url: ApiBaseUrlOption = None,
    api_token: ApiTokenOption = None,
    broadcast: BroadcastOption = False,
    bypass_confirmation: BypassConfirmationOption = False,
    json_output: JsonOption = False,
    source_type: SourceTypeOption = None,
    source_address: SourceAddressOption = None,
    auction_address: AuctionAddressOption = None,
    limit: LimitOption = None,
    sender: SenderOption = None,
    account: AccountOption = None,
    keystore: KeystoreOption = None,
    password_file: PasswordFileOption = None,
    verbose: VerboseOption = False,
) -> None:
    del verbose
    if bypass_confirmation and not broadcast:
        raise typer.BadParameter("--bypass-confirmation requires --broadcast", param_hint="--bypass-confirmation")
    cli_ctx = CLIContext(config, api_base_url=api_base_url, api_token=api_token)
    normalized_source_type = _normalize_source_type_filter(source_type)
    normalized_source_address = normalize_cli_address(source_address, param_hint="--source")
    normalized_auction_address = normalize_cli_address(auction_address, param_hint="--auction")
    exec_ctx = cli_ctx.resolve_execution(
        broadcast=broadcast,
        required_for="broadcast kick execution",
        sender=normalize_cli_address(sender, param_hint="--sender"),
        account_name=account,
        keystore_path=keystore,
        password_file=password_file,
    )
    payload = {
        "sourceType": normalized_source_type,
        "sourceAddress": normalized_source_address,
        "auctionAddress": normalized_auction_address,
        "limit": limit,
        "sender": exec_ctx.sender,
    }
    try:
        with cli_ctx.control_plane_client() as client:
            response = client.prepare_kicks(payload)
            data = response["data"]
            warnings = list(response.get("warnings") or [])
            broadcast_records: list[dict[str, object]] = []
            if broadcast and response["status"] == "ok":
                render_action_preview(data, heading="Prepared kick action")
                render_warnings(warnings)
                if not bypass_confirmation and not typer.confirm(
                    f"Broadcast {len(data.get('transactions') or [])} transaction(s) in returned order?",
                    default=False,
                ):
                    raise typer.Exit(code=2)
                if exec_ctx.signer is None or exec_ctx.sender is None:
                    raise typer.Exit(code=1)
                broadcast_records = execute_prepared_action_sync(
                    settings=cli_ctx.settings,
                    client=client,
                    action_id=str(data["actionId"]),
                    sender=exec_ctx.sender,
                    signer=exec_ctx.signer,
                    transactions=list(data.get("transactions") or []),
                )
    except ControlPlaneError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    if json_output:
        output = dict(data)
        if broadcast:
            output["broadcastRecords"] = broadcast_records
        emit_json("kick.run", status=response["status"], data=output, warnings=response.get("warnings"))
    else:
        if not broadcast:
            render_action_preview(data, heading="Prepared kick action")
            render_warnings(list(response.get("warnings") or []))
        if response["status"] == "noop":
            typer.echo("No kick transactions were prepared.")
        elif not broadcast:
            typer.echo("Dry run only. No transaction was sent.")
        else:
            render_broadcast_result(broadcast_records)

    if response["status"] == "noop":
        raise typer.Exit(code=2)
