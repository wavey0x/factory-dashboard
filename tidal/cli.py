"""CLI entrypoint for tidal."""

from __future__ import annotations

import asyncio

import typer

from tidal.auction_cli import app as auction_app
from tidal.cli_context import CLIContext
from tidal.cli_options import ConfigOption
from tidal.errors import ConfigurationError
from tidal.health import run_healthcheck
from tidal.logging import OutputMode, configure_logging
from tidal.logs_cli import app as logs_app
from tidal.migrations import run_migrations
from tidal.runtime import build_web3_client
from tidal.scan_cli import app as scan_app
from tidal.kick_cli import app as kick_app

app = typer.Typer(help="Tidal CLI")
db_app = typer.Typer(help="Database commands", no_args_is_help=True)

app.add_typer(db_app, name="db")
app.add_typer(scan_app, name="scan")
app.add_typer(auction_app, name="auction")
app.add_typer(kick_app, name="kick")
app.add_typer(logs_app, name="logs")


@db_app.command("migrate")
def db_migrate(config: ConfigOption = None) -> None:
    """Run Alembic migrations to create or update the schema."""

    configure_logging(output_mode=OutputMode.TEXT)
    cli_ctx = CLIContext(config)
    run_migrations(cli_ctx.settings.database_url)
    typer.echo("migrations applied")


@app.command("healthcheck")
def healthcheck(config: ConfigOption = None) -> None:
    """Check database and RPC connectivity."""

    configure_logging(output_mode=OutputMode.TEXT)
    cli_ctx = CLIContext(config)
    with cli_ctx.session() as session:
        web3_client = None
        if cli_ctx.settings.rpc_url:
            web3_client = build_web3_client(cli_ctx.settings)
        result = asyncio.run(run_healthcheck(session, web3_client))
    typer.echo(result)


if __name__ == "__main__":
    app()
