#!/usr/bin/env python3
"""Interactively enable relevant sell tokens on a freshly deployed auction."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(REPO_ROOT))

from eth_utils import to_checksum_address

from tidal.auction_migration.deploy_single_auction import (
    build_sync_web3,
    discover_local_keystore_path,
    maybe_load_signer,
    prompt_bool,
    prompt_optional_address,
    prompt_text,
    read_keystore_address,
)
from tidal.config import load_settings
from tidal.ops.auction_enable import (
    AuctionTokenEnabler,
    TokenProbe,
    format_probe_reason,
    parse_manual_token_input,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect a Yearn auction and queue enable(address) calls for relevant tokens.",
    )
    parser.add_argument("auction_address", nargs="?", default=None, help="Auction address to inspect")
    parser.add_argument("--config", type=Path, default=None, help="Optional config.yaml path.")
    parser.add_argument(
        "--extra-token",
        action="append",
        default=[],
        help="Extra token address to probe. Can be supplied multiple times.",
    )
    return parser.parse_args()


def print_auction_summary(inspection) -> None:  # noqa: ANN001
    print("Auction summary:")
    print(f"  auction       {to_checksum_address(inspection.auction_address)}")
    print(f"  governance    {to_checksum_address(inspection.governance)}")
    print(f"  receiver      {to_checksum_address(inspection.receiver)}")
    print(f"  want          {to_checksum_address(inspection.want)}")
    print(f"  version       {inspection.version or 'unknown'}")
    print(f"  in factory    {'yes' if inspection.in_configured_factory else 'no'}")
    print(
        "  yearn gov     "
        f"{'yes' if inspection.governance_matches_required else 'no'}"
    )
    print(f"  enabled now   {len(inspection.enabled_tokens)} token(s)")
    print()


def print_probe_table(probes: list[TokenProbe]) -> None:
    if not probes:
        print("No candidate tokens were discovered.")
        print()
        return

    print("Token probe results:")
    for index, probe in enumerate(probes, 1):
        balance = probe.normalized_balance if probe.normalized_balance is not None else "-"
        origins = ",".join(probe.origins) if probe.origins else "-"
        detail = f" ({probe.detail})" if probe.detail else ""
        print(
            f"  [{index:02d}] {probe.status:<8} {probe.display_label} | "
            f"balance={balance} | origins={origins} | {format_probe_reason(probe.reason)}{detail}"
        )
    print()


def prompt_token_selection(eligible: list[TokenProbe]) -> list[TokenProbe]:
    if not eligible:
        return []

    print("Eligible tokens:")
    for index, probe in enumerate(eligible, 1):
        balance = probe.normalized_balance or "?"
        print(f"  [{index:02d}] {probe.display_label} | balance={balance} | origins={','.join(probe.origins)}")
    print()

    while True:
        raw = prompt_text(
            "Skip any eligible token numbers (comma-separated, blank keeps all)",
            required=False,
        )
        if not raw:
            return eligible

        try:
            skip_indexes = {
                int(chunk.strip(), 10)
                for chunk in raw.split(",")
                if chunk.strip()
            }
        except ValueError:
            print("Enter token numbers like 1,3 or leave blank.")
            continue

        if any(index < 1 or index > len(eligible) for index in skip_indexes):
            print("One or more token numbers are out of range.")
            continue

        return [
            probe
            for index, probe in enumerate(eligible, 1)
            if index not in skip_indexes
        ]


def prompt_manual_tokens() -> list[str]:
    while True:
        raw = prompt_text(
            "Additional token addresses to probe (comma-separated, blank for none)",
            required=False,
        )
        if not raw:
            return []
        try:
            return parse_manual_token_input(raw)
        except Exception as exc:  # noqa: BLE001
            print(f"Invalid token list: {exc}")


def main() -> None:
    args = parse_args()
    settings = load_settings(args.config)
    w3 = build_sync_web3(settings)
    enabler = AuctionTokenEnabler(w3, settings)

    auction_address = args.auction_address
    if not auction_address:
        try:
            auction_address = prompt_text("Auction address", required=True)
        except EOFError as exc:
            raise SystemExit("Auction address is required.") from exc

    inspection = enabler.inspect_auction(auction_address)
    print_auction_summary(inspection)

    if not inspection.in_configured_factory:
        if not prompt_bool("Auction is not in the configured factory. Continue anyway?", default=False):
            print("Aborted.")
            return

    if not inspection.governance_matches_required:
        if not prompt_bool(
            "Auction governance does not match the configured Yearn trade handler. Continue anyway?",
            default=False,
        ):
            print("Aborted.")
            return

    source = enabler.resolve_source(inspection)
    print("Resolved source:")
    print(f"  type          {source.source_type}")
    print(f"  address       {to_checksum_address(source.source_address)}")
    print(f"  name          {source.source_name or 'unknown'}")
    print()

    for warning in source.warnings:
        print(f"Warning: {warning}")
    if source.warnings:
        print()

    manual_tokens = list(args.extra_token)
    manual_tokens.extend(prompt_manual_tokens())

    discovery = enabler.discover_tokens(
        inspection=inspection,
        source=source,
        manual_tokens=manual_tokens,
    )
    print(f"Discovered {len(discovery.tokens_by_address)} unique token candidate(s).")
    for note in discovery.notes:
        print(f"Note: {note}")
    if discovery.notes:
        print()

    probes = enabler.probe_tokens(
        inspection=inspection,
        source=source,
        discovery=discovery,
    )
    print_probe_table(probes)

    eligible = [probe for probe in probes if probe.status == "eligible"]
    if not eligible:
        print("No enable() calls need to be queued.")
        return

    selected = prompt_token_selection(eligible)
    if not selected:
        print("All eligible tokens were removed from the plan.")
        return

    selected_addresses = [probe.token_address for probe in selected]
    commands, state = enabler.build_enable_plan(
        inspection=inspection,
        tokens=selected_addresses,
    )

    default_keystore_path = discover_local_keystore_path(settings)
    default_preview_caller = read_keystore_address(default_keystore_path)

    print("Wei-roll plan:")
    print(f"  enable calls  {len(selected_addresses)}")
    print(f"  commands      {len(commands)}")
    print(f"  state slots   {len(state)}")
    print()

    if default_keystore_path is not None:
        print(f"Detected local keystore: {default_keystore_path}")
    use_live = prompt_bool(
        "Broadcast a live trade handler transaction?",
        default=default_keystore_path is not None,
    )
    signer = maybe_load_signer(settings, required=use_live)

    if signer is not None:
        preview_caller = signer.address
    else:
        preview_caller = prompt_optional_address(
            "Caller address for execute() preview",
            default=default_preview_caller,
        )

    if preview_caller:
        is_mech = enabler.is_authorized_mech(inspection.governance, preview_caller)
        print(
            "Preview caller mech authorization: "
            f"{'yes' if is_mech else 'no'} ({to_checksum_address(preview_caller)})"
        )
    else:
        print("Preview caller mech authorization: skipped")

    preview = enabler.preview_execution(
        trade_handler_address=inspection.governance,
        commands=commands,
        state=state,
        caller_address=preview_caller,
    )
    print("Preview:")
    print(f"  execute call  {'ok' if preview.call_succeeded else 'failed'}")
    print(f"  gas estimate  {preview.gas_estimate if preview.gas_estimate is not None else 'unavailable'}")
    if preview.error_message:
        print(f"  detail        {preview.error_message}")
    print()

    if not use_live:
        print("Dry run only. No transaction was sent.")
        return

    if signer is None:
        raise SystemExit("Signer is required for live execution.")

    if not preview.call_succeeded:
        if not prompt_bool("Preview failed. Send the transaction anyway?", default=False):
            print("Aborted before broadcast.")
            return

    if not prompt_bool("Send transaction now?", default=False):
        print("Aborted before broadcast.")
        return

    tx_hash, gas_estimate = enabler.send_execute_transaction(
        signer=signer,
        trade_handler_address=inspection.governance,
        commands=commands,
        state=state,
    )
    print("Transaction sent:")
    print(f"  tx hash       {tx_hash}")
    print(f"  gas estimate  {gas_estimate}")


if __name__ == "__main__":
    main()
