# CLI Reference

This reference is organized around the two executable roles in Tidal:

- `tidal`: the API-backed CLI client
- `tidal-server`: the server operator CLI

Both commands read the same home-based runtime layout by default:

- `~/.tidal/config.yaml`
- `~/.tidal/.env`
- `~/.tidal/auction_pricing_policy.yaml`

Run `tidal init` once on a machine before using either command.

## How To Use This Section

Start with the overview page for your role, then use the command-specific pages for exact workflows and flags.

| Role | Start here | Command groups |
|---|---|---|
| CLI client | [CLI Client Overview](cli-client-reference.md) | [`tidal init`](cli-client-init.md), [`tidal kick`](cli-client-kick.md), [`tidal auction`](cli-client-auction.md), [`tidal logs`](cli-client-logs.md) |
| Server operator | [Server Operator CLI Overview](cli-server-reference.md) | [`tidal-server db`](cli-server-db.md), [`tidal-server scan`](cli-server-scan.md), [`tidal-server api`](cli-server-api.md), [`tidal-server auth`](cli-server-auth.md), [`tidal-server kick`](cli-server-kick.md), [`tidal-server auction`](cli-server-auction.md), [`tidal-server logs`](cli-server-logs.md) |

## Shared Patterns

### Preview first

Mutating transaction commands default to preview mode. Add `--broadcast` to actually sign and send a transaction.

### Local signing

Broadcasting commands share the same wallet surface:

- `--sender`
- `--account`
- `--keystore`
- `--password-file`

The private key stays with the machine running the CLI.

### Machine-readable output

Most read and write commands accept `--json` for scripting and automation.

### Config overrides

Both executables support path overrides such as `--config` and the `TIDAL_*` environment variables documented in [Configuration](config.md).

## Choose The Right CLI

Use `tidal` when:

- you are a remote operator calling the hosted or self-hosted API
- you want the server to own shared state and audit history
- you want wallet signing to stay local to your workstation

Use `tidal-server` when:

- you are operating the host that owns the shared database
- you are running the scanner, API, or auth management
- you intentionally want transactions to execute from the server itself
