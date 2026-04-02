"""Shared CLI validation helpers."""

from __future__ import annotations

import typer


def require_no_confirmation_for_json(*, json_output: bool, no_confirmation: bool) -> None:
    """Require --no-confirmation when a mutating command emits JSON."""
    if json_output and not no_confirmation:
        raise typer.BadParameter(
            "--json requires --no-confirmation for transaction-sending commands.",
            param_hint="--json",
        )


def require_no_confirmation_for_unattended(*, no_confirmation: bool, command_name: str) -> None:
    """Require --no-confirmation for unattended mutation paths."""
    if not no_confirmation:
        raise typer.BadParameter(
            f"{command_name} requires --no-confirmation because it may send transactions unattended.",
            param_hint="--no-confirmation",
        )
