import json
from types import SimpleNamespace

import pytest
from eth_account import Account

from tidal.cli_support import (
    load_signer_from_options,
    resolve_keystore_path,
    resolve_sender_address,
    validate_sender_matches_signer,
)


@pytest.fixture
def wallet_fixture(tmp_path, monkeypatch):
    password = "test-password-123"
    account = Account.create()
    keystore_data = Account.encrypt(account.key, password)

    foundry_dir = tmp_path / ".foundry" / "keystores"
    foundry_dir.mkdir(parents=True)
    account_keystore = foundry_dir / "ops"
    account_keystore.write_text(json.dumps(keystore_data), encoding="utf-8")

    explicit_keystore = tmp_path / "explicit-keystore.json"
    explicit_keystore.write_text(json.dumps(keystore_data), encoding="utf-8")

    password_file = tmp_path / "keystore-password.txt"
    password_file.write_text(password, encoding="utf-8")

    monkeypatch.setattr("tidal.cli_support.foundry_keystore_dir", lambda: foundry_dir)

    settings = SimpleNamespace(
        txn_keystore_path=None,
        txn_keystore_passphrase=None,
    )
    return SimpleNamespace(
        account=account,
        account_keystore=account_keystore,
        explicit_keystore=explicit_keystore,
        password=password,
        password_file=password_file,
        settings=settings,
    )


def test_resolve_keystore_path_uses_account_name(wallet_fixture) -> None:
    resolved = resolve_keystore_path(
        wallet_fixture.settings,
        account_name="ops",
        required=True,
        required_for="broadcast test",
    )

    assert resolved == wallet_fixture.account_keystore


def test_resolve_keystore_path_rejects_account_and_keystore_together(wallet_fixture) -> None:
    with pytest.raises(SystemExit, match="Specify only one of --account or --keystore"):
        resolve_keystore_path(
            wallet_fixture.settings,
            account_name="ops",
            keystore_path=wallet_fixture.explicit_keystore,
            required=True,
            required_for="broadcast test",
        )


def test_load_signer_from_options_uses_password_file(wallet_fixture) -> None:
    signer = load_signer_from_options(
        wallet_fixture.settings,
        required=True,
        required_for="broadcast test",
        account_name="ops",
        password_file=wallet_fixture.password_file,
    )

    assert signer is not None
    assert signer.address == wallet_fixture.account.address.lower()


def test_resolve_sender_address_prefers_explicit_sender(wallet_fixture) -> None:
    resolved = resolve_sender_address(
        wallet_fixture.settings,
        sender="0x1111111111111111111111111111111111111111",
        account_name="ops",
    )

    assert resolved == "0x1111111111111111111111111111111111111111"


def test_validate_sender_matches_signer_rejects_mismatch(wallet_fixture) -> None:
    signer = load_signer_from_options(
        wallet_fixture.settings,
        required=True,
        required_for="broadcast test",
        keystore_path=wallet_fixture.explicit_keystore,
        password_file=wallet_fixture.password_file,
    )

    with pytest.raises(SystemExit, match="does not match signer address"):
        validate_sender_matches_signer(
            sender="0x1111111111111111111111111111111111111111",
            signer=signer,
            required_for="broadcast test",
        )
