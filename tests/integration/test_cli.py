from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import tidal.kick_cli as kick_cli_module
from tidal.cli import app


def _write_txn_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"db_path: {tmp_path / 'test.db'}\nrpc_url: https://example-rpc.invalid\n",
        encoding="utf-8",
    )
    return config_path


class _FakeTxnService:
    async def run_once(self, **kwargs):  # noqa: ANN003
        return SimpleNamespace(
            run_id="run-1",
            status="DRY_RUN",
            candidates_found=0,
            kicks_attempted=0,
            kicks_succeeded=0,
            kicks_failed=0,
            failure_summary={},
        )


class _FakeWeb3Client:
    async def get_base_fee(self) -> int:
        return 0


class _StopDaemon(Exception):
    pass


def test_scan_run_requires_rpc_url(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("RPC_URL", raising=False)
    config_path = tmp_path / "config.yaml"
    config_path.write_text("RPC_URL: ''\nDB_PATH: ./test.db\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["scan", "run", "--config", str(config_path)])

    assert result.exit_code == 1
    assert "RPC_URL is required" in result.output


def test_scan_run_requires_keystore_when_auto_settle_enabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RPC_URL", "https://example-rpc.invalid")
    monkeypatch.delenv("TXN_KEYSTORE_PATH", raising=False)
    monkeypatch.delenv("TXN_KEYSTORE_PASSPHRASE", raising=False)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "db_path: ./test.db\nscan_auto_settle_enabled: true\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["scan", "run", "--config", str(config_path)])

    assert result.exit_code == 1
    assert "TXN_KEYSTORE_PATH and TXN_KEYSTORE_PASSPHRASE are required" in result.output


def test_kick_rejects_invalid_source_address() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["kick", "run", "--source", "not-an-address"])

    assert result.exit_code != 0
    assert "invalid address" in result.output


def test_kick_rejects_invalid_auction_address() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["kick", "run", "--auction", "not-an-address"])

    assert result.exit_code != 0
    assert "invalid address" in result.output


@pytest.mark.parametrize(
    ("flag_args", "expected"),
    [
        ([], None),
        (["--require-curve-quote"], True),
        (["--allow-missing-curve-quote"], False),
    ],
)
def test_kick_threads_curve_quote_override(tmp_path, monkeypatch, flag_args, expected) -> None:
    config_path = _write_txn_config(tmp_path)
    captured = {}

    def fake_build_txn_service(settings, session, **kwargs):  # noqa: ANN001, ANN003
        del settings, session
        captured["require_curve_quote"] = kwargs.get("require_curve_quote")
        return _FakeTxnService()

    monkeypatch.setattr(kick_cli_module, "build_txn_service", fake_build_txn_service)
    monkeypatch.setattr(kick_cli_module, "configure_logging", lambda *args, **kwargs: None)
    monkeypatch.setattr(kick_cli_module, "_load_run_rows", lambda session, run_id: [])

    runner = CliRunner()
    result = runner.invoke(app, ["kick", "run", "--json", "--config", str(config_path), *flag_args])

    assert result.exit_code == 2
    assert captured["require_curve_quote"] is expected


@pytest.mark.parametrize(
    ("flag_args", "expected"),
    [
        ([], None),
        (["--require-curve-quote"], True),
        (["--allow-missing-curve-quote"], False),
    ],
)
def test_kick_daemon_threads_curve_quote_override(tmp_path, monkeypatch, flag_args, expected) -> None:
    config_path = _write_txn_config(tmp_path)
    captured = {}

    def fake_build_txn_service(settings, session, **kwargs):  # noqa: ANN001, ANN003
        del settings, session
        captured["require_curve_quote"] = kwargs.get("require_curve_quote")
        return _FakeTxnService()

    async def fake_sleep(_seconds: int | float) -> None:
        raise _StopDaemon()

    monkeypatch.setattr(kick_cli_module, "build_txn_service", fake_build_txn_service)
    monkeypatch.setattr(kick_cli_module, "configure_logging", lambda *args, **kwargs: None)
    monkeypatch.setattr(kick_cli_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(kick_cli_module, "_load_run_rows", lambda session, run_id: [])
    monkeypatch.setattr("tidal.cli_context.build_web3_client", lambda settings: _FakeWeb3Client())

    runner = CliRunner()
    result = runner.invoke(app, ["kick", "daemon", "--config", str(config_path), *flag_args])

    assert isinstance(result.exception, _StopDaemon)
    assert captured["require_curve_quote"] is expected


def test_auction_enable_tokens_requires_rpc_url(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RPC_URL", "")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("db_path: ./test.db\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["auction", "enable-tokens", "0x1111111111111111111111111111111111111111", "--config", str(config_path)],
    )

    assert result.exit_code == 1
    assert "RPC_URL is required" in result.output


def test_auction_enable_tokens_rejects_invalid_extra_token() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "auction",
            "enable-tokens",
            "0x1111111111111111111111111111111111111111",
            "--extra-token",
            "not-an-address",
        ],
    )

    assert result.exit_code != 0
    assert "invalid address" in result.output


def test_auction_enable_tokens_rejects_invalid_caller() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "auction",
            "enable-tokens",
            "0x1111111111111111111111111111111111111111",
            "--caller",
            "not-an-address",
        ],
    )

    assert result.exit_code != 0
    assert "invalid address" in result.output
