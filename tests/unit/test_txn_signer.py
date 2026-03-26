"""Unit tests for transaction signer."""

import json
import tempfile
from pathlib import Path

import pytest
from eth_account import Account

from tidal.errors import ConfigurationError
from tidal.transaction_service.signer import TransactionSigner


@pytest.fixture
def keystore_fixture(tmp_path):
    """Create a temporary keystore file and return (path, passphrase, address)."""
    passphrase = "test-passphrase-123"
    account = Account.create()
    keystore_data = Account.encrypt(account.key, passphrase)
    keystore_path = tmp_path / "keystore.json"
    keystore_path.write_text(json.dumps(keystore_data), encoding="utf-8")
    return str(keystore_path), passphrase, account.address.lower()


def test_signer_loads_keystore(keystore_fixture):
    path, passphrase, expected_address = keystore_fixture
    signer = TransactionSigner(path, passphrase)
    assert signer.address == expected_address


def test_signer_checksum_address(keystore_fixture):
    path, passphrase, expected_address = keystore_fixture
    signer = TransactionSigner(path, passphrase)
    assert signer.checksum_address.lower() == expected_address
    assert signer.checksum_address != expected_address  # checksum has mixed case



def test_signer_rejects_bad_passphrase(keystore_fixture):
    path, _, _ = keystore_fixture
    with pytest.raises(Exception):
        TransactionSigner(path, "wrong-passphrase")


def test_signer_rejects_missing_keystore():
    with pytest.raises(Exception):
        TransactionSigner("/nonexistent/path/keystore.json", "passphrase")


def test_sign_transaction(keystore_fixture):
    path, passphrase, _ = keystore_fixture
    signer = TransactionSigner(path, passphrase)

    tx = {
        "to": "0x0000000000000000000000000000000000000001",
        "value": 0,
        "gas": 21000,
        "maxFeePerGas": 50 * 10**9,
        "maxPriorityFeePerGas": 2 * 10**9,
        "nonce": 0,
        "chainId": 1,
        "type": 2,
        "data": b"",
    }
    raw_bytes = signer.sign_transaction(tx)
    assert isinstance(raw_bytes, bytes)
    assert len(raw_bytes) > 0
