"""Shared helpers for interactive CLI workflows."""

from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
from typing import Any

from web3 import HTTPProvider, Web3

from tidal.normalizers import normalize_address
from tidal.transaction_service.signer import TransactionSigner


def build_sync_web3(settings: Any) -> Web3:
    if not settings.rpc_url:
        raise SystemExit("RPC_URL is required")
    return Web3(
        HTTPProvider(
            settings.rpc_url,
            request_kwargs={"timeout": settings.rpc_timeout_seconds},
        )
    )


def foundry_keystore_dir() -> Path:
    return Path.home() / ".foundry" / "keystores"


def discover_local_keystore_path(settings: Any) -> Path | None:
    configured = getattr(settings, "resolved_txn_keystore_path", None)
    if configured is not None:
        if configured.is_file():
            return configured

    foundry_dir = foundry_keystore_dir()
    if not foundry_dir.is_dir():
        return None

    for preferred_name in ("wavey3", "wavey2"):
        candidate = foundry_dir / preferred_name
        if candidate.is_file():
            return candidate

    keystores = sorted(path for path in foundry_dir.iterdir() if path.is_file())
    if len(keystores) == 1:
        return keystores[0]
    return None


def resolve_keystore_path(
    settings: Any,
    *,
    keystore_path: str | Path | None = None,
    required: bool = False,
    required_for: str = "transaction execution",
) -> Path | None:
    if keystore_path is not None:
        resolved = Path(keystore_path).expanduser()
        if resolved.is_file():
            return resolved
        raise SystemExit(f"Keystore file not found for {required_for}: {resolved}")

    configured = getattr(settings, "resolved_txn_keystore_path", None)
    if configured:
        resolved = Path(configured).expanduser()
        if resolved.is_file():
            return resolved
        raise SystemExit(f"Configured keystore file not found for {required_for}: {resolved}")

    discovered = discover_local_keystore_path(settings)
    if discovered is not None:
        return discovered

    if required:
        raise SystemExit(
            f"A wallet is required for {required_for}. "
            "Provide --keystore, configure TXN_KEYSTORE_PATH, or install a local Foundry keystore."
        )

    return None


def _read_password_file(password_file: str | Path, *, required_for: str) -> str:
    resolved = Path(password_file).expanduser()
    if not resolved.is_file():
        raise SystemExit(f"Password file not found for {required_for}: {resolved}")
    value = resolved.read_text(encoding="utf-8").strip()
    if value:
        return value
    raise SystemExit(f"Password file is empty for {required_for}: {resolved}")


def resolve_keystore_password(
    settings: Any,
    *,
    password_file: str | Path | None = None,
    passphrase: str | None = None,
    prompt_if_missing: bool = False,
    required_for: str = "transaction execution",
) -> str | None:
    if passphrase is not None:
        return passphrase

    if password_file is not None:
        return _read_password_file(password_file, required_for=required_for)

    if settings.txn_keystore_passphrase:
        return settings.txn_keystore_passphrase

    env_value = os.getenv("ETH_PASSWORD")
    if env_value:
        return env_value

    if prompt_if_missing:
        return getpass.getpass("Keystore password: ")

    return None


def load_signer_from_options(
    settings: Any,
    *,
    required: bool,
    required_for: str = "transaction execution",
    keystore_path: str | Path | None = None,
    password_file: str | Path | None = None,
    passphrase: str | None = None,
) -> TransactionSigner | None:
    resolved_keystore_path = resolve_keystore_path(
        settings,
        keystore_path=keystore_path,
        required=required,
        required_for=required_for,
    )
    if resolved_keystore_path is None:
        return None

    resolved_password = resolve_keystore_password(
        settings,
        password_file=password_file,
        passphrase=passphrase,
        prompt_if_missing=required,
        required_for=required_for,
    )
    if not resolved_password:
        if required:
            raise SystemExit(f"Keystore password is required for {required_for}.")
        return None

    return TransactionSigner(str(resolved_keystore_path), resolved_password)


def read_keystore_address(keystore_path: Path | None) -> str | None:
    if keystore_path is None or not keystore_path.is_file():
        return None
    try:
        payload = json.loads(keystore_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None

    address = payload.get("address")
    if not address:
        return None
    if not str(address).startswith("0x"):
        address = f"0x{address}"
    try:
        return normalize_address(address)
    except Exception:  # noqa: BLE001
        return None


def maybe_load_signer(
    settings: Any,
    *,
    required: bool,
    required_for: str = "transaction execution",
    keystore_path: str | Path | None = None,
    passphrase: str | None = None,
) -> TransactionSigner | None:
    try:
        return load_signer_from_options(
            settings,
            required=required,
            required_for=required_for,
            keystore_path=keystore_path,
            passphrase=passphrase,
        )
    except SystemExit:
        if not required:
            return None
        raise


def resolve_sender_address(
    settings: Any,
    *,
    keystore_path: str | Path | None = None,
    signer: TransactionSigner | None = None,
) -> str | None:
    if signer is not None:
        return normalize_address(signer.address)
    resolved_keystore_path = resolve_keystore_path(
        settings,
        keystore_path=keystore_path,
        required=False,
    )
    return read_keystore_address(resolved_keystore_path)
