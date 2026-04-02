# Runtime Simplification Plan

## Goal

Simplify the server CLI to a small supported runtime surface:

- `tidal-server api serve`
- `tidal-server scan run`
- `tidal-server kick run`

Scheduling and orchestration are outside the scope of this repo.

## Decisions

- `scan run` is read-only by default.
- Scan auto-settle is enabled only with `--auto-settle`.
- `--auto-settle` requires `--no-confirmation`.
- Remove `scan_auto_settle_enabled` from config and templates.
- Remove `scan daemon`.
- Remove `kick daemon`.
- Do not add `kick run --batch` in this change.

## Desired CLI Semantics

### `tidal-server scan run`

- Read-only by default.
- `--auto-settle --no-confirmation` enables settlement for that invocation.
- Auto-settle also requires transaction credentials.
- No config fallback.
- No `--no-auto-settle`.

### `tidal-server kick run`

- Remains the one-shot kick execution command.
- `--no-confirmation` remains the unattended execution switch.

### Removed Commands

- `tidal-server scan daemon`
- `tidal-server kick daemon`

## Implementation Work

### 1. Simplify scan auto-settle control

- Add `--auto-settle` to `scan run`.
- Treat the flag as the only way to enable scan-side settlement.
- Require `--no-confirmation` whenever `--auto-settle` is present.
- Require transaction credentials whenever `--auto-settle` is present.
- Thread the flag through scan runtime construction explicitly.

Acceptance criteria:

- `tidal-server scan run` stays read-only.
- `tidal-server scan run --auto-settle` fails without `--no-confirmation`.
- `tidal-server scan run --auto-settle --no-confirmation` enables settlement.

### 2. Remove config-driven auto-settle and daemon-only config

- Delete `scan_auto_settle_enabled`.
- Delete `scan_interval_seconds`.
- Remove any now-unused interval CLI option if it only exists for daemon commands.
- Update config templates and config docs to match.

Acceptance criteria:

- `server.yaml` no longer includes scan auto-settle or daemon interval settings.
- Runtime config no longer implies scan mutation on its own.

### 3. Remove daemon commands

- Delete `scan daemon`.
- Delete `kick daemon`.
- Remove help text, examples, and docs that describe them as supported commands.

Acceptance criteria:

- `tidal-server scan --help` no longer lists `daemon`.
- `tidal-server kick --help` no longer lists `daemon`.

### 4. Tighten docs around the supported CLI surface

Update:

- `RUN.md`
- `README.md`
- `docs/cli-server-scan.md`
- `docs/cli-server-kick.md`
- `docs/config.md`
- any other docs that still describe daemon mode or config-driven scan auto-settle

Docs should show:

- `scan run` is read-only unless `--auto-settle` is passed
- `kick run` is the supported one-shot kick path
- scheduler details are external and not the focus of repo docs

### 5. Verification

Minimum verification:

1. Help output reflects the reduced CLI surface.
2. `scan run` is read-only by default.
3. `scan run --auto-settle` requires `--no-confirmation`.
4. `scan run --auto-settle --no-confirmation` still requires transaction credentials.
5. Docs and config templates no longer mention removed commands or removed settings.

Suggested tests:

- CLI validation coverage for `scan run`
- regression coverage for scan runtime behavior with and without `--auto-settle`

## Non-Goals

- Do not add `kick run --batch`.
- Do not redesign kick batching behavior in this pass.
- Do not merge kick execution into scan.
- Do not document or implement scheduler-specific setup in this repo.
