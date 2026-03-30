from tidal.config import load_settings
from tidal.control_plane.outbox import default_action_report_outbox_path
from tidal.paths import default_txn_lock_path


def _clear_runtime_env(monkeypatch) -> None:
    for key in (
        "RPC_URL",
        "DB_PATH",
        "TXN_KEYSTORE_PATH",
        "TXN_KEYSTORE_PASSPHRASE",
        "TIDAL_HOME",
        "TIDAL_CONFIG",
        "TIDAL_ENV_FILE",
        "TIDAL_PRICING_PATH",
        "TIDAL_OPERATOR_STATE_DIR",
    ):
        monkeypatch.delenv(key, raising=False)


def test_load_settings_defaults_to_tidal_home_paths(tmp_path, monkeypatch) -> None:
    home_root = tmp_path / "home"
    app_home = home_root / ".tidal"
    app_home.mkdir(parents=True)
    (app_home / "config.yaml").write_text(
        "db_path: state/custom.db\n"
        "txn_keystore_path: keys/ops.json\n",
        encoding="utf-8",
    )
    (app_home / ".env").write_text("RPC_URL=https://example-rpc.invalid\n", encoding="utf-8")

    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("HOME", str(home_root))

    settings = load_settings()

    assert settings.resolved_home_path == app_home
    assert settings.resolved_config_path == app_home / "config.yaml"
    assert settings.resolved_env_path == app_home / ".env"
    assert settings.resolved_pricing_path == app_home / "pricing.yaml"
    assert settings.resolved_db_path == app_home / "state" / "custom.db"
    assert settings.resolved_txn_keystore_path == app_home / "keys" / "ops.json"
    assert settings.rpc_url == "https://example-rpc.invalid"


def test_load_settings_uses_tidal_config_override_and_config_local_env(tmp_path, monkeypatch) -> None:
    home_root = tmp_path / "home"
    home_root.mkdir(parents=True)
    app_home = home_root / ".tidal"
    app_home.mkdir()
    (app_home / "config.yaml").write_text("db_path: state/home.db\n", encoding="utf-8")
    (app_home / ".env").write_text("RPC_URL=https://home.invalid\n", encoding="utf-8")

    config_dir = tmp_path / "custom-config"
    config_dir.mkdir()
    config_path = config_dir / "operator.yaml"
    config_path.write_text(
        "db_path: state/override.db\n"
        "txn_keystore_path: keys/override.json\n",
        encoding="utf-8",
    )
    (config_dir / ".env").write_text("RPC_URL=https://config-dir.invalid\n", encoding="utf-8")

    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("HOME", str(home_root))
    monkeypatch.setenv("TIDAL_CONFIG", str(config_path))

    settings = load_settings()

    assert settings.resolved_config_path == config_path
    assert settings.resolved_env_path == config_dir / ".env"
    assert settings.resolved_db_path == config_dir / "state" / "override.db"
    assert settings.resolved_txn_keystore_path == config_dir / "keys" / "override.json"
    assert settings.rpc_url == "https://config-dir.invalid"


def test_load_settings_uses_explicit_env_and_pricing_overrides(tmp_path, monkeypatch) -> None:
    home_root = tmp_path / "home"
    app_home = home_root / ".tidal"
    app_home.mkdir(parents=True)
    (app_home / "config.yaml").write_text("db_path: state/home.db\n", encoding="utf-8")
    (app_home / ".env").write_text("RPC_URL=https://home.invalid\n", encoding="utf-8")

    explicit_env_path = tmp_path / "secrets.env"
    explicit_env_path.write_text("RPC_URL=https://override.invalid\n", encoding="utf-8")
    explicit_policy_path = tmp_path / "custom-pricing.yaml"
    explicit_policy_path.write_text("profiles: {}\n", encoding="utf-8")

    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("HOME", str(home_root))
    monkeypatch.setenv("TIDAL_ENV_FILE", str(explicit_env_path))
    monkeypatch.setenv("TIDAL_PRICING_PATH", str(explicit_policy_path))

    settings = load_settings()

    assert settings.resolved_env_path == explicit_env_path
    assert settings.resolved_pricing_path == explicit_policy_path
    assert settings.rpc_url == "https://override.invalid"


def test_default_db_path_uses_tidal_home_when_config_omits_db_path(tmp_path, monkeypatch) -> None:
    home_root = tmp_path / "home"
    app_home = home_root / ".tidal"
    app_home.mkdir(parents=True)
    config_dir = tmp_path / "config-dir"
    config_dir.mkdir()
    config_path = config_dir / "config.yaml"
    config_path.write_text("chain_id: 1\n", encoding="utf-8")

    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("HOME", str(home_root))

    settings = load_settings(config_path)

    assert settings.resolved_db_path == app_home / "state" / "tidal.db"
    assert settings.tidal_api_base_url == "https://api.tidal.wavey.info"


def test_default_outbox_and_lock_paths_live_under_tidal_home(tmp_path, monkeypatch) -> None:
    home_root = tmp_path / "home"
    _clear_runtime_env(monkeypatch)
    monkeypatch.setenv("HOME", str(home_root))

    app_home = home_root / ".tidal"
    assert default_action_report_outbox_path() == app_home / "state" / "operator" / "action_outbox.db"
    assert default_txn_lock_path() == app_home / "run" / "txn_daemon.lock"
