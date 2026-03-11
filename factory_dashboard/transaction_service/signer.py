"""Keystore decryption and transaction signing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eth_account import Account
from eth_utils import to_checksum_address

from factory_dashboard.normalizers import normalize_address


class TransactionSigner:
    """Decrypts a UTC/JSON keystore at startup and signs transactions."""

    def __init__(
        self,
        keystore_path: str,
        passphrase: str,
    ):
        keystore_data = json.loads(Path(keystore_path).read_text(encoding="utf-8"))
        private_key = Account.decrypt(keystore_data, passphrase)
        self._account = Account.from_key(private_key)
        self._address = normalize_address(self._account.address)

    @property
    def address(self) -> str:
        return self._address

    @property
    def checksum_address(self) -> str:
        return to_checksum_address(self._address)

    def sign_transaction(self, tx: dict[str, Any]) -> bytes:
        signed = self._account.sign_transaction(tx)
        return bytes(signed.raw_transaction)
