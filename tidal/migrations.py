"""Alembic migration helpers."""

from __future__ import annotations

from alembic import command
from alembic.config import Config

from tidal.resources import migration_resource_paths


def run_migrations(database_url: str) -> None:
    with migration_resource_paths() as (alembic_ini, script_location):
        config = Config(str(alembic_ini))
        config.set_main_option("script_location", str(script_location))
        config.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(config, "head")
