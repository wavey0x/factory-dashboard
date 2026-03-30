from typer.testing import CliRunner

from tidal.cli import app as operator_app
from tidal.server_cli import app as server_app


def test_operator_cli_does_not_expose_scan_or_db_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(operator_app, ["--help"])

    assert result.exit_code == 0
    assert "scan" not in result.output
    assert "db" not in result.output
    assert "logs" in result.output
    assert "kick" in result.output
    assert "auction" in result.output
    assert "init" in result.output


def test_server_cli_exposes_scan_db_and_api_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(server_app, ["--help"])

    assert result.exit_code == 0
    assert "scan" in result.output
    assert "db" in result.output
    assert "api" in result.output


def test_operator_init_creates_tidal_home_layout(tmp_path, monkeypatch) -> None:
    app_home = tmp_path / "operator-home"
    monkeypatch.delenv("TIDAL_OPERATOR_STATE_DIR", raising=False)
    monkeypatch.setenv("TIDAL_HOME", str(app_home))

    runner = CliRunner()
    result = runner.invoke(operator_app, ["init"])

    assert result.exit_code == 0
    assert (app_home / "config.yaml").is_file()
    assert (app_home / ".env").is_file()
    assert (app_home / "auction_pricing_policy.yaml").is_file()
    assert (app_home / "state").is_dir()
    assert (app_home / "state" / "operator").is_dir()
    assert (app_home / "run").is_dir()
    assert "Config:" in result.output
    assert str(app_home / "config.yaml") in result.output
