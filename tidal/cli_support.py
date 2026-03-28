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


def prompt_text(label: str, *, default: str | None = None, required: bool = True) -> str:
    while True:
        suffix = f" [{default}]" if default not in {None, ""} else ""
        raw = input(f"{label}{suffix}: ").strip()
        if raw:
            return raw
        if default is not None:
            return default
        if not required:
            return ""
        print("Value is required.")


def prompt_address(label: str, *, default: str | None = None) -> str:
    while True:
        value = prompt_text(label, default=default)
        try:
            return normalize_address(value)
        except Exception as exc:  # noqa: BLE001
            print(f"Invalid address: {exc}")


def prompt_optional_address(label: str, *, default: str | None = None) -> str | None:
    while True:
        value = prompt_text(label, default=default, required=False)
        if not value:
            return None
        try:
            return normalize_address(value)
        except Exception as exc:  # noqa: BLE001
            print(f"Invalid address: {exc}")


def prompt_uint(label: str, *, default: int | None = None) -> int:
    while True:
        raw = prompt_text(label, default=str(default) if default is not None else None)
        try:
            value = int(raw, 10)
        except ValueError:
            print("Enter a base-10 integer.")
            continue
        if value < 0:
            print("Value must be non-negative.")
            continue
        return value


def prompt_bool(label: str, *, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{label} [{hint}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Enter y or n.")


def discover_local_keystore_path(settings: Any) -> Path | None:
    if settings.txn_keystore_path:
        configured = Path(settings.txn_keystore_path).expanduser()
        if configured.is_file():
            return configured

    foundry_dir = Path.home() / ".foundry" / "keystores"
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
    required_for: str = "live execution",
) -> Path | None:
    if keystore_path is not None:
        resolved = Path(keystore_path).expanduser()
        if resolved.is_file():
            return resolved
        raise SystemExit(f"Keystore file not found for {required_for}: {resolved}")

    discovered = discover_local_keystore_path(settings)
    if discovered is not None:
        return discovered

    configured = settings.txn_keystore_path
    if configured:
        resolved = Path(configured).expanduser()
        if resolved.is_file():
            return resolved
        raise SystemExit(f"Configured keystore file not found for {required_for}: {resolved}")

    if required:
        raise SystemExit(f"Keystore path is required for {required_for}.")

    return None


def resolve_keystore_passphrase(
    settings: Any,
    *,
    passphrase_env: str | None = None,
    passphrase: str | None = None,
    prompt_if_missing: bool = False,
    required_for: str = "live execution",
) -> str | None:
    if passphrase is not None:
        return passphrase

    if passphrase_env:
        env_value = os.getenv(passphrase_env)
        if env_value:
            return env_value
        raise SystemExit(f"Environment variable {passphrase_env} is not set for {required_for}.")

    if settings.txn_keystore_passphrase:
        return settings.txn_keystore_passphrase

    if prompt_if_missing:
        return getpass.getpass("Keystore passphrase: ")

    return None


def load_signer_from_options(
    settings: Any,
    *,
    required: bool,
    required_for: str = "live execution",
    keystore_path: str | Path | None = None,
    passphrase_env: str | None = None,
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

    resolved_passphrase = resolve_keystore_passphrase(
        settings,
        passphrase_env=passphrase_env,
        passphrase=passphrase,
        prompt_if_missing=required,
        required_for=required_for,
    )
    if not resolved_passphrase:
        if required:
            raise SystemExit(f"Keystore passphrase is required for {required_for}.")
        return None

    return TransactionSigner(str(resolved_keystore_path), resolved_passphrase)


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
    required_for: str = "live execution",
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
