"""Kick command group."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict, is_dataclass

import typer
from sqlalchemy import select

from tidal.cli_context import CLIContext, normalize_cli_address
from tidal.cli_exit_codes import kick_exit_code
from tidal.cli_options import (
    AuctionAddressOption,
    ConfigOption,
    JsonOption,
    KeystoreOption,
    LimitOption,
    NoConfirmationOption,
    PasswordFileOption,
    SourceAddressOption,
    SourceTypeOption,
    VerboseOption,
)
from tidal.cli_validation import require_no_confirmation_for_json
from tidal.cli_renderers import (
    BroadcastRecord,
    emit_json,
    kick_scope_label,
    render_broadcast_records,
    render_kick_inspect,
    render_kick_run_summary,
    render_kick_submission_summary,
)
from tidal.errors import ConfigurationError
from tidal.logging import OutputMode, configure_logging
from tidal.ops.kick_inspect import inspect_kick_candidates
from tidal.persistence import models
from tidal.runtime import build_txn_service
from tidal.transaction_service.types import SourceType, TransactionExecutionReport

app = typer.Typer(help="Kick auction lots", no_args_is_help=True)


def _to_dict(value: object) -> dict[str, object]:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    raise TypeError("unsupported result payload")


def _normalize_source_type_filter(value: str | None) -> SourceType | None:
    if value is None:
        return None
    normalized = value.strip().lower().replace("-", "_")
    if normalized in {"strategy", "fee_burner"}:
        return normalized  # type: ignore[return-value]
    raise typer.BadParameter("expected 'strategy' or 'fee-burner'", param_hint="--source-type")


def _load_run_rows(session, run_id: str) -> list[dict[str, object]]:
    stmt = select(models.kick_txs).where(models.kick_txs.c.run_id == run_id).order_by(models.kick_txs.c.id.asc())
    return [dict(row) for row in session.execute(stmt).mappings().all()]


def _make_confirm_fn() -> Callable[[dict], bool]:
    """Return a confirm callback that displays a batch summary."""

    def _confirm_batch(summary: dict) -> bool:
        batch_size = summary["batch_size"]
        render_kick_submission_summary(summary)
        prompt = "Send this transaction?" if batch_size == 1 else f"Send batch of {batch_size} kicks?"
        return typer.confirm(prompt, default=False)

    return _confirm_batch


def _make_execution_report_fn() -> Callable[[TransactionExecutionReport], None]:
    """Return a callback that renders the live transaction result panel immediately."""

    def _render_execution_report(report: TransactionExecutionReport) -> None:
        typer.echo()
        render_broadcast_records(
            [
                BroadcastRecord(
                    operation=report.operation,
                    sender=report.sender,
                    tx_hash=report.tx_hash,
                    broadcast_at=report.broadcast_at,
                    chain_id=report.chain_id,
                    receipt_status=report.receipt_status,
                    block_number=report.block_number,
                    gas_used=report.gas_used,
                    gas_estimate=report.gas_estimate,
                )
            ]
        )

    return _render_execution_report


@app.command("run")
def kick_run(
    config: ConfigOption = None,
    no_confirmation: NoConfirmationOption = False,
    json_output: JsonOption = False,
    source_type: SourceTypeOption = None,
    source_address: SourceAddressOption = None,
    auction_address: AuctionAddressOption = None,
    limit: LimitOption = None,
    keystore: KeystoreOption = None,
    password_file: PasswordFileOption = None,
    verbose: VerboseOption = False,
    explain: bool = typer.Option(False, "--explain", help="Show explainability details for the selected candidates."),
    require_curve_quote: bool | None = typer.Option(
        None,
        "--require-curve-quote/--allow-missing-curve-quote",
        help="Override Curve quote strictness for this run.",
    ),
) -> None:
    """Evaluate kick candidates and send transactions after review."""

    configure_logging(verbose=verbose, output_mode=OutputMode.TEXT)
    require_no_confirmation_for_json(json_output=json_output, no_confirmation=no_confirmation)
    cli_ctx = CLIContext(config, mode="server")
    normalized_source_type = _normalize_source_type_filter(source_type)
    normalized_source_address = normalize_cli_address(source_address, param_hint="--source")
    normalized_auction_address = normalize_cli_address(auction_address, param_hint="--auction")
    try:
        cli_ctx.require_rpc()
    except ConfigurationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    exec_ctx = cli_ctx.resolve_execution(
        required=True,
        required_for="kick execution",
        keystore_path=keystore,
        password_file=password_file,
    )

    inspection_data = None
    if explain:
        with cli_ctx.session() as session:
            inspection_data = inspect_kick_candidates(
                session,
                cli_ctx.settings,
                source_type=normalized_source_type,
                source_address=normalized_source_address,
                auction_address=normalized_auction_address,
                limit=limit,
            )

    confirm_fn = None if no_confirmation else _make_confirm_fn()
    execution_report_fn = _make_execution_report_fn() if not json_output else None
    skip_base_fee_check = False
    web3_client = cli_ctx.web3_client()
    base_fee_wei = asyncio.run(web3_client.get_base_fee())
    base_fee_gwei = base_fee_wei / 1e9
    if base_fee_gwei > cli_ctx.settings.txn_max_base_fee_gwei:
        typer.echo(f"Warning: base fee is {base_fee_gwei:.2f} gwei (limit: {cli_ctx.settings.txn_max_base_fee_gwei} gwei)")
        if no_confirmation:
            skip_base_fee_check = True
        else:
            typer.confirm("Continue despite high gas?", default=False, abort=True)
            skip_base_fee_check = True

    if not json_output:
        typer.echo(f"Evaluating {kick_scope_label(normalized_source_type, source_address=normalized_source_address, auction_address=normalized_auction_address)}...")

    with cli_ctx.session() as session:
        txn_service = build_txn_service(
            cli_ctx.settings,
            session,
            confirm_fn=confirm_fn,
            execution_report_fn=execution_report_fn,
            require_curve_quote=require_curve_quote,
            skip_base_fee_check=skip_base_fee_check,
            web3_client=web3_client,
            signer=exec_ctx.signer,
        )
        result = asyncio.run(
            txn_service.run_once(
                live=True,
                batch=False,
                source_type=normalized_source_type,
                source_address=normalized_source_address,
                auction_address=normalized_auction_address,
                limit=limit,
            )
        )
        run_rows = _load_run_rows(session, result.run_id)

    status = "ok"
    if result.candidates_found == 0:
        status = "noop"
    elif result.kicks_failed and result.kicks_succeeded:
        status = "error"
    elif result.kicks_failed:
        status = "error"

    execution_sender = exec_ctx.sender
    if json_output:
        data = {
            "run": _to_dict(result),
            "rows": run_rows,
            "sender": execution_sender,
        }
        if inspection_data is not None:
            data["inspection"] = asdict(inspection_data)
        emit_json("kick.run", status=status, data=data)
    else:
        render_kick_run_summary(
            result=result,
            live=True,
            source_type=normalized_source_type,
            source_address=normalized_source_address,
            auction_address=normalized_auction_address,
            run_rows=run_rows,
            verbose=verbose,
            sender=execution_sender,
            show_broadcast_records=execution_report_fn is None,
        )
        if inspection_data is not None:
            typer.echo()
            render_kick_inspect(inspection_data, show_all=True)

    raise typer.Exit(code=kick_exit_code(
        live=True,
        status=result.status,
        candidates_found=result.candidates_found,
        kicks_failed=result.kicks_failed,
    ))


@app.command("inspect")
def kick_inspect(
    config: ConfigOption = None,
    json_output: JsonOption = False,
    source_type: SourceTypeOption = None,
    source_address: SourceAddressOption = None,
    auction_address: AuctionAddressOption = None,
    limit: LimitOption = None,
    show_all: bool = typer.Option(False, "--show-all", help="Show deferred and limited candidates in addition to ready/cooldown."),
) -> None:
    """Explain why candidates are ready, skipped, or deferred."""

    configure_logging(output_mode=OutputMode.TEXT)
    cli_ctx = CLIContext(config, mode="server")
    normalized_source_type = _normalize_source_type_filter(source_type)
    normalized_source_address = normalize_cli_address(source_address, param_hint="--source")
    normalized_auction_address = normalize_cli_address(auction_address, param_hint="--auction")

    with cli_ctx.session() as session:
        result = inspect_kick_candidates(
            session,
            cli_ctx.settings,
            source_type=normalized_source_type,
            source_address=normalized_source_address,
            auction_address=normalized_auction_address,
            limit=limit,
        )

    status = "ok" if (result.ready_count or result.cooldown_count or result.deferred_same_auction_count or result.limited_count) else "noop"
    if json_output:
        emit_json("kick.inspect", status=status, data=asdict(result))
    else:
        render_kick_inspect(result, show_all=show_all)
    raise typer.Exit(code=0 if status == "ok" else 2)
