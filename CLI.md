# CLI Implementation Spec

## Goal

Make Tidal usable as a real `uv` tool from any directory without relying on:

- a project-local virtualenv
- repo-root `config.yaml`
- repo-root `.env`
- repo-root `auction_pricing_policy.yaml`
- repo-root Alembic assets at runtime

The target user experience is:

```bash
uv tool install --editable /path/to/tidal
uv tool update-shell
tidal init
tidal --help
tidal-server --help
```

Later, after packaging cleanup:

```bash
uv tool install git+ssh://git@github.com/wavey0x/tidal.git
uvx --from git+ssh://git@github.com/wavey0x/tidal.git tidal --help
```

## Final Decisions

These are implementation decisions, not options.

### 1. Default app home

Use:

```text
~/.tidal
```

Optional override:

- `TIDAL_HOME`

No XDG split. Keep it simple.

### 2. Default file layout

Use:

```text
~/.tidal/
  config.yaml
  .env
  auction_pricing_policy.yaml
  state/
    tidal.db
    operator/
      action_outbox.db
  run/
    txn_daemon.lock
```

### 3. Default command model

Primary install model:

- `uv tool install`

Primary local-dev install model:

- `uv tool install --editable /path/to/tidal`

`uvx` is supported only after packaging cleanup is complete.

### 4. No backward compatibility for repo-root discovery

Make a clean break.

Do not preserve implicit discovery of:

- `Path.cwd() / config.yaml`
- `Path.cwd() / auction_pricing_policy.yaml`
- repo-root `.env` via ambient `load_dotenv()`

If a user wants repo-local config during development, they must pass `--config` explicitly or set `TIDAL_HOME`.

### 5. Relative config paths

Relative paths defined inside config must resolve from the config file directory, not `cwd`.

This applies at minimum to:

- `db_path`
- `txn_keystore_path`

### 6. Runtime assets must be package resources

Before blessing non-editable installs, move runtime assets into the package and load them as package resources.

This applies at minimum to:

- `alembic.ini`
- `alembic/`
- `config.yaml` template
- `env.template`
- `auction_pricing_policy.yaml` template

### 7. One init command

Add:

```bash
tidal init
```

That is the only initialization command required.

It should scaffold `~/.tidal` by default.

## Out Of Scope

Do not do any of this in this project:

- preserve repo-root config auto-discovery
- add migration shims for old cwd defaults
- add XDG-only layout complexity
- add a custom installer outside `uv`
- redesign the CLI entrypoints
- add multiple init/config subcommands unless clearly needed later

## Required Environment Variables

Add these as the supported path controls:

- `TIDAL_HOME`
- `TIDAL_CONFIG`
- `TIDAL_ENV_FILE`
- `TIDAL_PRICING_POLICY_PATH`

Keep existing non-path env vars as they are.

## Required Runtime Behavior

### Path resolution order

Config path:

1. `--config`
2. `TIDAL_CONFIG`
3. `TIDAL_HOME/config.yaml`
4. `~/.tidal/config.yaml`

Env file:

1. current process environment
2. `TIDAL_ENV_FILE`
3. `<config_dir>/.env`
4. `TIDAL_HOME/.env`
5. `~/.tidal/.env`

Pricing policy path:

1. explicit argument from caller
2. `TIDAL_PRICING_POLICY_PATH`
3. `<config_dir>/auction_pricing_policy.yaml`
4. `TIDAL_HOME/auction_pricing_policy.yaml`
5. `~/.tidal/auction_pricing_policy.yaml`

Database path:

1. `db_path` from config if present
2. otherwise `TIDAL_HOME/state/tidal.db`
3. otherwise `~/.tidal/state/tidal.db`

Relative paths in config always resolve from `<config_dir>`.

### `tidal init`

`tidal init` must:

- create `~/.tidal/`
- create `~/.tidal/state/`
- create `~/.tidal/state/operator/`
- create `~/.tidal/run/`
- write `config.yaml` if missing
- write `.env` if missing
- write `auction_pricing_policy.yaml` if missing
- print resolved paths
- support `--force` to overwrite templates

It does not need to create the SQLite DB file itself.

## File-Level Implementation Plan

### 1. Add shared path helpers

Create:

- `tidal/paths.py`

Implement:

- `tidal_home() -> Path`
- `default_config_path() -> Path`
- `default_env_path() -> Path`
- `default_pricing_policy_path() -> Path`
- `default_state_dir() -> Path`
- `default_db_path() -> Path`
- `default_operator_state_dir() -> Path`
- `default_action_outbox_path() -> Path`
- `default_run_dir() -> Path`
- `default_txn_lock_path() -> Path`

Rules:

- always return expanded absolute paths
- do not inspect `cwd`

### 2. Refactor config loading

Update:

- [tidal/config.py](./tidal/config.py)

Required changes:

- stop using `_DEFAULT_CONFIG_PATH = Path("config.yaml")`
- stop calling bare `load_dotenv()`
- add explicit config/env path resolution
- make `Settings` or the settings wrapper remember the resolved config path
- change `resolved_db_path` to resolve relative paths from `config_path.parent`
- do the same for `txn_keystore_path`

Implementation note:

The simplest shape is:

- keep `Settings` as the data model
- add a small resolved wrapper or private metadata fields for:
  - loaded config path
  - loaded env path
  - loaded pricing policy path

### 3. Refactor pricing policy lookup

Update:

- [tidal/transaction_service/pricing_policy.py](./tidal/transaction_service/pricing_policy.py)
- [tidal/runtime.py](./tidal/runtime.py)

Required changes:

- stop defaulting to `Path.cwd() / "auction_pricing_policy.yaml"`
- make runtime pass an explicit resolved pricing-policy path into:
  - `load_auction_pricing_policy()`
  - `load_token_sizing_policy()`

Those functions should no longer guess from `cwd`.

### 4. Move operator outbox into shared state tree

Update:

- [tidal/control_plane/outbox.py](./tidal/control_plane/outbox.py)

Required changes:

- replace hardcoded `~/.tidal/operator-state` default
- use the shared path helper
- default to `~/.tidal/state/operator/action_outbox.db`

`TIDAL_OPERATOR_STATE_DIR` can stay only if it is still useful after the refactor. It is optional, not required.

### 5. Move lock file into run dir

Update:

- [tidal/runtime.py](./tidal/runtime.py)

Required change:

- stop deriving `txn_daemon.lock` from `settings.resolved_db_path.parent`
- use `~/.tidal/run/txn_daemon.lock` via the shared path helper

### 6. Package Alembic and runtime templates

Update:

- [tidal/migrations.py](./tidal/migrations.py)
- [pyproject.toml](./pyproject.toml)

Add package resources under something like:

- `tidal/_resources/alembic.ini`
- `tidal/_resources/alembic/...`
- `tidal/_resources/templates/config.yaml`
- `tidal/_resources/templates/env.template`
- `tidal/_resources/templates/auction_pricing_policy.yaml`

Required changes:

- load Alembic config and script location from packaged resources
- include those resources in the wheel build

### 7. Add `tidal init`

Update:

- [tidal/cli.py](./tidal/cli.py)

Add:

- `init` command

Implementation:

- use the shared path helpers
- read templates from packaged resources
- write files only when missing unless `--force` is passed
- create required directories

Do not add a separate `config init` subtree unless the simple top-level command proves insufficient.

### 8. Update docs

Update at minimum:

- [README.md](./README.md)
- [docs/index.md](./docs/index.md)
- [docs/local-dev.md](./docs/local-dev.md)
- [docs/operator-guide.md](./docs/operator-guide.md)
- [docs/server-ops.md](./docs/server-ops.md)
- [docs/config.md](./docs/config.md)
- [docs/cli-reference.md](./docs/cli-reference.md)

Required doc changes:

- document `uv tool install --editable ...` as the local-dev install path
- document `tidal init`
- document `~/.tidal`
- stop telling users to rely on repo-root `.env` and `config.yaml`
- stop showing venv-specific systemd `ExecStart` examples as the preferred deployment pattern

## Testing Requirements

### Unit tests

Add tests for:

- `TIDAL_HOME` resolution
- `TIDAL_CONFIG` override
- `TIDAL_ENV_FILE` override
- `TIDAL_PRICING_POLICY_PATH` override
- default config/env/policy/db paths under `~/.tidal`
- relative `db_path` resolution against config dir
- relative `txn_keystore_path` resolution against config dir
- outbox default path under `~/.tidal/state/operator`
- lock path under `~/.tidal/run`

### Integration tests

Add tests that:

1. create a fake home directory
2. write `~/.tidal/config.yaml`, `.env`, and `auction_pricing_policy.yaml`
3. run the same CLI command from two unrelated working directories
4. assert identical resolved paths and behavior

This is the key regression test for "works from any repository".

### Packaging smoke tests

Add a packaging smoke test that:

1. builds the distribution
2. installs it into an isolated environment or tool environment
3. runs:
   - `tidal --help`
   - `tidal-server --help`
   - `tidal init --force`
   - `tidal-server db migrate` against a temp DB

This is what will catch missing Alembic or template resources.

## Acceptance Criteria

The work is done when all of the following are true:

1. `uv tool install --editable /path/to/tidal` produces working `tidal` and `tidal-server` commands from any directory.
2. With no `--config`, Tidal uses `~/.tidal/config.yaml` and `~/.tidal/.env`.
3. `db_path: state/tidal.db` inside `~/.tidal/config.yaml` resolves relative to `~/.tidal/`, not `cwd`.
4. Relative `txn_keystore_path` in config resolves relative to the config file.
5. Pricing policy is loaded from `~/.tidal/auction_pricing_policy.yaml` or an explicit override, not from `cwd`.
6. The outbox default is `~/.tidal/state/operator/action_outbox.db`.
7. The daemon lock default is `~/.tidal/run/txn_daemon.lock`.
8. `tidal init` creates the expected directory and template layout.
9. `tidal-server db migrate` works from a non-editable install.
10. Docs no longer require a project-local virtualenv or repo-root config files for normal usage.

## Recommended Implementation Order

Do the work in this order:

1. `tidal/paths.py`
2. config loading and relative-path resolution
3. pricing policy lookup
4. outbox and lock path cleanup
5. package Alembic and templates
6. `tidal init`
7. docs
8. packaging smoke tests

This order keeps the path model stable before the init command and docs are added.
