"""Helpers for accessing packaged runtime resources."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from importlib.resources import as_file, files
from pathlib import Path
from typing import Iterator

_RESOURCES_PACKAGE = "tidal._resources"


def read_template_text(filename: str) -> str:
    resource = files(_RESOURCES_PACKAGE).joinpath("templates").joinpath(filename)
    return resource.read_text(encoding="utf-8")


@contextmanager
def migration_resource_paths() -> Iterator[tuple[Path, Path]]:
    resource_root = files(_RESOURCES_PACKAGE)
    with ExitStack() as stack:
        alembic_ini = stack.enter_context(as_file(resource_root.joinpath("alembic.ini")))
        script_location = stack.enter_context(as_file(resource_root.joinpath("alembic")))
        yield Path(alembic_ini), Path(script_location)
