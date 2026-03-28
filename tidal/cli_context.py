"""Shared CLI context helpers."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from tidal.cli_support import (
    build_sync_web3,
    load_signer_from_options,
    read_keystore_address,
    resolve_keystore_path,
)
from tidal.config import Settings, load_settings
from tidal.errors import ConfigurationError
from tidal.normalizers import normalize_address
from tidal.persistence.db import Database
from tidal.runtime import build_web3_client

if TYPE_CHECKING:
    from collections.abc import Iterator

    from web3 import Web3

    from tidal.chain.web3_client import Web3Client
    from tidal.transaction_service.signer import TransactionSigner


@dataclass(slots=True)
class CLIContext:
    config_path: Path | None = None
    settings: Settings = field(init=False)

    def __post_init__(self) -> None:
        self.settings = load_settings(self.config_path)

    def require_rpc(self) -> None:
        if not self.settings.rpc_url:
            raise ConfigurationError("RPC_URL is required for this command")

    @contextmanager
    def session(self) -> "Iterator[object]":
        db = Database(self.settings.database_url)
        with db.session() as session:
            yield session

    def sync_web3(self) -> "Web3":
        self.require_rpc()
        return build_sync_web3(self.settings)

    def web3_client(self) -> "Web3Client":
        self.require_rpc()
        return build_web3_client(self.settings)

    def resolve_signer(
        self,
        *,
        required: bool,
        required_for: str,
        keystore_path: str | Path | None = None,
        passphrase_env: str | None = None,
    ) -> "TransactionSigner | None":
        return load_signer_from_options(
            self.settings,
            required=required,
            required_for=required_for,
            keystore_path=keystore_path,
            passphrase_env=passphrase_env,
        )

    def resolved_keystore_path(self, *, keystore_path: str | Path | None = None) -> Path | None:
        return resolve_keystore_path(
            self.settings,
            keystore_path=keystore_path,
            required=False,
        )

    def resolve_preview_caller(
        self,
        *,
        caller: str | None = None,
        keystore_path: str | Path | None = None,
        signer: "TransactionSigner | None" = None,
    ) -> str | None:
        if signer is not None:
            return signer.address
        if caller is not None:
            return normalize_address(caller)
        resolved_keystore = self.resolved_keystore_path(keystore_path=keystore_path)
        return read_keystore_address(resolved_keystore)
