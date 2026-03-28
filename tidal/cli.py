"""Operator CLI entrypoint for API-backed Tidal commands."""

from __future__ import annotations

import typer

from tidal.operator_auction_cli import app as auction_app
from tidal.operator_kick_cli import app as kick_app
from tidal.operator_logs_cli import app as logs_app

app = typer.Typer(help="Tidal operator CLI")

app.add_typer(auction_app, name="auction")
app.add_typer(kick_app, name="kick")
app.add_typer(logs_app, name="logs")


if __name__ == "__main__":
    app()

