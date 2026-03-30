from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from tidal.cli import app as operator_app
import tidal.operator_auction_cli as operator_auction_cli_module


def _write_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("db_path: ./test.db\n", encoding="utf-8")
    return config_path


class _EnableTokensClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __enter__(self) -> "_EnableTokensClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        del exc_type, exc, tb

    def prepare_enable_tokens(self, auction_address: str, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append((auction_address, payload))
        return {
            "status": "ok",
            "warnings": ["execution reverted: !authorized"],
            "data": {
                "actionId": "action-enable",
                "actionType": "enable_tokens",
                "preview": {
                    "inspection": {
                        "auction_address": auction_address,
                        "governance": "0xb634316e06cc0b358437cbadd4dc94f1d3a92b3b",
                        "want": "0x1111111111111111111111111111111111111111",
                        "receiver": "0x2222222222222222222222222222222222222222",
                        "version": "1.0.0",
                        "in_configured_factory": True,
                        "governance_matches_required": True,
                        "enabled_tokens": [],
                    },
                    "source": {
                        "source_type": "strategy",
                        "source_address": "0x3333333333333333333333333333333333333333",
                        "source_name": "Test Strategy",
                    },
                    "probes": [
                        {
                            "token_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                            "symbol": "CRV",
                            "status": "eligible",
                            "reasonLabel": "eligible",
                        }
                    ],
                    "selectedTokens": ["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
                    "commandsCount": 1,
                    "stateSlots": 2,
                    "preview": {
                        "call_succeeded": False,
                        "gas_estimate": 215036,
                        "error_message": "execution reverted: !authorized",
                    },
                },
                "transactions": [
                    {
                        "operation": "enable-tokens",
                        "to": "0xb634316e06cc0b358437cbadd4dc94f1d3a92b3b",
                        "data": "0xdeadbeef",
                        "value": "0x0",
                        "chainId": 1,
                        "sender": payload["sender"],
                        "gasEstimate": 215036,
                        "gasLimit": 258043,
                    }
                ],
            },
        }


class _NoopEnableTokensClient:
    def __enter__(self) -> "_NoopEnableTokensClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        del exc_type, exc, tb

    def prepare_enable_tokens(self, auction_address: str, payload: dict[str, object]) -> dict[str, object]:
        del auction_address, payload
        return {
            "status": "noop",
            "warnings": [],
            "data": {
                "preview": {},
                "transactions": [],
            },
        }


class _NoopSettleClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __enter__(self) -> "_NoopSettleClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        del exc_type, exc, tb

    def prepare_settle(self, auction_address: str, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append((auction_address, payload))
        return {
            "status": "noop",
            "warnings": [],
            "data": {
                "preview": {
                    "decision": {
                        "status": "noop",
                        "operation_type": None,
                        "token_address": "0xd533a949740bb3306d119cc777fa900ba034cd52",
                        "reason": "auction still active above minimumPrice",
                    },
                    "inspection": {
                        "auction_address": auction_address,
                        "is_active_auction": True,
                        "active_token": "0xd533a949740bb3306d119cc777fa900ba034cd52",
                        "active_tokens": ["0xd533a949740bb3306d119cc777fa900ba034cd52"],
                        "active_available_raw": 984634876557164,
                        "active_price_public_raw": 35392170414952578,
                        "minimum_price_public_raw": 354,
                        "minimum_price_scaled_1e18": 354,
                    },
                },
                "transactions": [],
            },
        }


def test_operator_auction_enable_tokens_uses_styled_submission_flow(tmp_path, monkeypatch) -> None:
    config_path = _write_config(tmp_path)
    client = _EnableTokensClient()

    monkeypatch.setattr(
        operator_auction_cli_module.CLIContext,
        "control_plane_client",
        lambda self, auth=True: client,
    )
    monkeypatch.setattr(
        operator_auction_cli_module.CLIContext,
        "resolve_execution",
        lambda self, **kwargs: SimpleNamespace(
            signer=SimpleNamespace(),
            sender="0x9999999999999999999999999999999999999999",
        ),
    )
    monkeypatch.setattr(operator_auction_cli_module.typer, "confirm", lambda *args, **kwargs: True)

    def fake_execute_prepared_action_sync(**kwargs):  # noqa: ANN003
        return [
            {
                "operation": kwargs["transactions"][0]["operation"],
                "sender": kwargs["sender"],
                "txHash": "0x" + "1" * 64,
                "broadcastAt": "2026-03-29T00:00:00+00:00",
                "chainId": 1,
                "gasEstimate": kwargs["transactions"][0]["gasEstimate"],
                "receiptStatus": "CONFIRMED",
                "blockNumber": 12345,
                "gasUsed": 210000,
            }
        ]

    monkeypatch.setattr(
        operator_auction_cli_module,
        "execute_prepared_action_sync",
        fake_execute_prepared_action_sync,
    )

    runner = CliRunner()
    result = runner.invoke(
        operator_app,
        [
            "auction",
            "enable-tokens",
            "0xe92af59d00becd5f70d2ba11ae1a74751503a185",
            "--broadcast",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert client.calls[0][0] == "0xe92af59d00becd5f70d2ba11ae1a74751503a185"
    assert "Prepared action" in result.output
    assert "enable-tokens · 1 transaction" in result.output
    assert "Review details" in result.output
    assert "Auction:" in result.output
    assert "Tokens:" in result.output
    assert "Warnings" in result.output
    assert "Submitting transaction..." in result.output
    assert "Confirmed" in result.output
    assert "Explorer:" not in result.output
    assert "Block:" not in result.output
    assert "Gas used:" not in result.output
    assert "Gas estimate:" not in result.output


def test_operator_auction_enable_tokens_noop_skips_prepared_panel(tmp_path, monkeypatch) -> None:
    config_path = _write_config(tmp_path)
    client = _NoopEnableTokensClient()

    monkeypatch.setattr(
        operator_auction_cli_module.CLIContext,
        "control_plane_client",
        lambda self, auth=True: client,
    )
    monkeypatch.setattr(
        operator_auction_cli_module.CLIContext,
        "resolve_execution",
        lambda self, **kwargs: SimpleNamespace(signer=None, sender=None),
    )

    runner = CliRunner()
    result = runner.invoke(
        operator_app,
        [
            "auction",
            "enable-tokens",
            "0xe92af59d00becd5f70d2ba11ae1a74751503a185",
            "--broadcast",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 2
    assert "Prepared action" not in result.output
    assert "No Transaction Prepared" in result.output
    assert "No transaction was prepared." in result.output


def test_operator_auction_settle_noop_shows_reason_and_price_state(tmp_path, monkeypatch) -> None:
    config_path = _write_config(tmp_path)
    client = _NoopSettleClient()

    monkeypatch.setattr(
        operator_auction_cli_module.CLIContext,
        "control_plane_client",
        lambda self, auth=True: client,
    )
    monkeypatch.setattr(
        operator_auction_cli_module.CLIContext,
        "resolve_execution",
        lambda self, **kwargs: SimpleNamespace(signer=None, sender=None),
    )

    runner = CliRunner()
    result = runner.invoke(
        operator_app,
        [
            "auction",
            "settle",
            "0xeb3746f59befef1f5834239fb65a2a4d88fdb251",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 2
    assert "No Transaction Prepared" in result.output
    assert "No transaction was prepared." in result.output
    assert "Reason:        auction still active above minimumPrice" in result.output
    assert "Settlement state" in result.output
    assert "Active token:" in result.output
    assert "0xd533a949740bb3306d119cc777fa900ba034cd52" in result.output
    assert "Available:     984634876557164" in result.output
    assert "Live price:    35392170414952578" in result.output
    assert "Floor price:   354" in result.output
    assert "Min price:     354 (scaled 1e18)" in result.output


def test_operator_auction_settle_sweep_threads_payload(tmp_path, monkeypatch) -> None:
    config_path = _write_config(tmp_path)
    client = _NoopSettleClient()

    monkeypatch.setattr(
        operator_auction_cli_module.CLIContext,
        "control_plane_client",
        lambda self, auth=True: client,
    )
    monkeypatch.setattr(
        operator_auction_cli_module.CLIContext,
        "resolve_execution",
        lambda self, **kwargs: SimpleNamespace(signer=None, sender=None),
    )

    runner = CliRunner()
    result = runner.invoke(
        operator_app,
        [
            "auction",
            "settle",
            "0xeb3746f59befef1f5834239fb65a2a4d88fdb251",
            "--sweep",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 2
    assert client.calls == [
        (
            "0xeb3746f59befef1f5834239fb65a2a4d88fdb251",
            {
                "sender": None,
                "tokenAddress": None,
                "sweep": True,
            },
        )
    ]
