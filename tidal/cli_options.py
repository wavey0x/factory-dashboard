"""Reusable Typer option definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

ConfigOption = Annotated[
    Path | None,
    typer.Option(
        "--config",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Optional config.yaml path.",
    ),
]

JsonOption = Annotated[
    bool,
    typer.Option(
        "--json",
        help="Emit machine-readable JSON output.",
    ),
]

LiveOption = Annotated[
    bool,
    typer.Option(
        "--live",
        help="Broadcast or persist a live transaction.",
    ),
]

YesOption = Annotated[
    bool,
    typer.Option(
        "--yes",
        help="Skip interactive confirmation.",
    ),
]

VerboseOption = Annotated[
    bool,
    typer.Option(
        "--verbose",
        help="Show extra diagnostic detail.",
    ),
]

IntervalOption = Annotated[
    int | None,
    typer.Option(
        "--interval-seconds",
        min=1,
        help="Seconds between daemon cycles.",
    ),
]

KeystoreOption = Annotated[
    Path | None,
    typer.Option(
        "--keystore",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Override signer keystore path.",
    ),
]

PassphraseEnvOption = Annotated[
    str | None,
    typer.Option(
        "--passphrase-env",
        help="Environment variable that contains the keystore passphrase.",
    ),
]

CallerOption = Annotated[
    str | None,
    typer.Option(
        "--caller",
        help="Override caller address for preview execution.",
    ),
]

SourceTypeOption = Annotated[
    str | None,
    typer.Option(
        "--type",
        help="Filter by source type: strategy or fee-burner.",
    ),
]

SourceAddressOption = Annotated[
    str | None,
    typer.Option(
        "--source",
        help="Filter to a specific source address.",
    ),
]

AuctionAddressOption = Annotated[
    str | None,
    typer.Option(
        "--auction",
        help="Filter to a specific auction address.",
    ),
]

LimitOption = Annotated[
    int | None,
    typer.Option(
        "--limit",
        min=1,
        help="Limit the number of selected candidates.",
    ),
]
