# CLI Reference

This page is derived from the live Typer command tree via `tidal --help` and `tidal-server --help`.

## Operator CLI: `tidal`

Top-level commands:

- `auction`
- `kick`
- `logs`

### `tidal auction`

Subcommands:

- `deploy`
- `enable-tokens`
- `settle`

#### `tidal auction deploy`

```bash
tidal auction deploy \
  --want <token> \
  --receiver <address> \
  --starting-price <int> \
  [--factory <address>] \
  [--governance <address>] \
  [--salt <hex>] \
  [--broadcast] \
  [--bypass-confirmation] \
  [--sender <address>] \
  [--account <name> | --keystore <file>] \
  [--password-file <file>] \
  [--json]
```

Shared API options:

- `--config`
- `--api-base-url`
- `--api-key`

#### `tidal auction enable-tokens`

```bash
tidal auction enable-tokens <auction> \
  [--extra-token <address>] \
  [--broadcast] \
  [--bypass-confirmation] \
  [--sender <address>] \
  [--account <name> | --keystore <file>] \
  [--password-file <file>] \
  [--json]
```

#### `tidal auction settle`

```bash
tidal auction settle <auction> \
  [--token <address>] \
  [--method auto|settle|sweep-and-settle] \
  [--broadcast] \
  [--bypass-confirmation] \
  [--sender <address>] \
  [--account <name> | --keystore <file>] \
  [--password-file <file>] \
  [--json]
```

### `tidal kick`

Subcommands:

- `inspect`
- `run`

#### `tidal kick inspect`

```bash
tidal kick inspect \
  [--source-type strategy|fee-burner] \
  [--source <address>] \
  [--auction <address>] \
  [--limit <n>] \
  [--show-all] \
  [--json]
```

Shared API options:

- `--config`
- `--api-base-url`
- `--api-key`

#### `tidal kick run`

```bash
tidal kick run \
  [--source-type strategy|fee-burner] \
  [--source <address>] \
  [--auction <address>] \
  [--limit <n>] \
  [--broadcast] \
  [--bypass-confirmation] \
  [--sender <address>] \
  [--account <name> | --keystore <file>] \
  [--password-file <file>] \
  [--verbose] \
  [--require-curve-quote | --allow-missing-curve-quote] \
  [--json]
```

### `tidal logs`

Subcommands:

- `kicks`
- `scans`
- `show`

#### `tidal logs kicks`

```bash
tidal logs kicks \
  [--source <address>] \
  [--auction <address>] \
  [--status <status>] \
  [--limit <n>] \
  [--json]
```

#### `tidal logs scans`

```bash
tidal logs scans \
  [--status <status>] \
  [--limit <n>] \
  [--json]
```

#### `tidal logs show`

```bash
tidal logs show <run_id> [--json]
```

## Server/Admin CLI: `tidal-server`

Top-level commands:

- `db`
- `scan`
- `auction`
- `kick`
- `logs`
- `api`
- `auth`

### `tidal-server db`

Subcommands:

- `migrate`

```bash
tidal-server db migrate [--config]
```

### `tidal-server scan`

Subcommands:

- `run`
- `daemon`

```bash
tidal-server scan run [--config] [--json]
tidal-server scan daemon [--config] [--interval-seconds <n>] [--json]
```

### `tidal-server auction`

Subcommands:

- `deploy`
- `enable-tokens`
- `settle`

```bash
tidal-server auction deploy \
  --want <token> \
  --receiver <address> \
  [--factory <address>] \
  [--governance <address>] \
  [--starting-price <int>] \
  [--salt <hex>] \
  [--broadcast] \
  [--bypass-confirmation] \
  [--sender <address>] \
  [--account <name> | --keystore <file>] \
  [--password-file <file>] \
  [--json]
```

```bash
tidal-server auction enable-tokens <auction> \
  [--extra-token <address>] \
  [--broadcast] \
  [--bypass-confirmation] \
  [--sender <address>] \
  [--account <name> | --keystore <file>] \
  [--password-file <file>] \
  [--json]
```

```bash
tidal-server auction settle <auction> \
  [--token <address>] \
  [--method auto|settle|sweep-and-settle] \
  [--broadcast] \
  [--bypass-confirmation] \
  [--sender <address>] \
  [--account <name> | --keystore <file>] \
  [--password-file <file>] \
  [--receipt-timeout <seconds>] \
  [--json]
```

### `tidal-server kick`

Subcommands:

- `run`
- `daemon`
- `inspect`

```bash
tidal-server kick run \
  [--source-type strategy|fee-burner] \
  [--source <address>] \
  [--auction <address>] \
  [--limit <n>] \
  [--broadcast] \
  [--bypass-confirmation] \
  [--sender <address>] \
  [--account <name> | --keystore <file>] \
  [--password-file <file>] \
  [--verbose] \
  [--explain] \
  [--require-curve-quote | --allow-missing-curve-quote] \
  [--json]
```

```bash
tidal-server kick daemon \
  [--source-type strategy|fee-burner] \
  [--source <address>] \
  [--auction <address>] \
  [--limit <n>] \
  [--interval-seconds <n>] \
  [--broadcast] \
  [--sender <address>] \
  [--account <name> | --keystore <file>] \
  [--password-file <file>] \
  [--verbose] \
  [--require-curve-quote | --allow-missing-curve-quote] \
  [--json]
```

```bash
tidal-server kick inspect \
  [--source-type strategy|fee-burner] \
  [--source <address>] \
  [--auction <address>] \
  [--limit <n>] \
  [--show-all] \
  [--json]
```

### `tidal-server logs`

Subcommands:

- `kicks`
- `scans`
- `show`

```bash
tidal-server logs kicks [--source <address>] [--auction <address>] [--status <status>] [--limit <n>] [--json]
tidal-server logs scans [--status <status>] [--limit <n>] [--json]
tidal-server logs show <run_id> [--json]
```

### `tidal-server api`

Subcommands:

- `serve`

```bash
tidal-server api serve [--config]
```

### `tidal-server auth`

Subcommands:

- `create`
- `list`
- `revoke`

```bash
tidal-server auth create --label <operator-label> [--config]
tidal-server auth list [--config]
tidal-server auth revoke <label> [--config]
```

## Shared Patterns

### JSON output

Most commands accept `--json` for machine-readable output.

### Wallet selection

Broadcasting commands accept one of:

- `--account <foundry-keystore-name>`
- `--keystore <path>`

and optionally:

- `--password-file <path>`

### Preview-first behavior

Mutating commands default to preview mode. Add `--broadcast` to actually send a transaction.

### Confirmation bypass

Use `--bypass-confirmation` only when you intentionally want non-interactive broadcasting.
