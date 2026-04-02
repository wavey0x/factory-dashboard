# CLI Reference

This is the single command-map page for Tidal. Use it to find the exact command page quickly.

Setup and workflow guidance live elsewhere:

- setup: [Install](install.md)
- CLI-client workflows: [CLI Client Guide](operator-guide.md)
- server workflows: [Server Operator Guide](server-ops.md)

## Shared Patterns

### Confirmation first

Mutating transaction commands send transactions after review by default. Use `--no-confirmation` only for unattended or machine-driven execution.

### Local signing

Broadcasting commands share the same wallet surface:

- `--sender`
- `--account`
- `--keystore`
- `--password-file`

The private key stays with the machine running the CLI.

### Machine-readable output

Most read and write commands accept `--json` for scripting and automation. On mutating commands, `--json` requires `--no-confirmation`.

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

## CLI Client Commands

| Command | Use it when | Reference |
|---|---|---|
| `tidal init` | You are bootstrapping a workstation or refreshing scaffold files | [CLI Client: `tidal init`](cli-client-init.md) |
| `tidal kick` | You want to inspect or execute kick candidates through the API | [CLI Client: `tidal kick`](cli-client-kick.md) |
| `tidal auction` | You want to deploy, enable, or settle auctions through the API | [CLI Client: `tidal auction`](cli-client-auction.md) |
| `tidal logs` | You want historical kick and scan data from the API | [CLI Client: `tidal logs`](cli-client-logs.md) |

## Server Operator Commands

| Command | Use it when | Reference |
|---|---|---|
| `tidal-server db` | You need to apply migrations | [Server Operator: `tidal-server db`](cli-server-db.md) |
| `tidal-server scan` | You need to run one scan cycle or an explicit scan-side auto-settle pass | [Server Operator: `tidal-server scan`](cli-server-scan.md) |
| `tidal-server api` | You need to serve the FastAPI control plane | [Server Operator: `tidal-server api`](cli-server-api.md) |
| `tidal-server auth` | You need to create, list, or revoke API keys | [Server Operator: `tidal-server auth`](cli-server-auth.md) |
| `tidal-server kick` | You want to inspect or execute kicks directly from the server | [Server Operator: `tidal-server kick`](cli-server-kick.md) |
| `tidal-server auction` | You want to manage auctions directly from the server | [Server Operator: `tidal-server auction`](cli-server-auction.md) |
| `tidal-server logs` | You want local operational history from the shared database | [Server Operator: `tidal-server logs`](cli-server-logs.md) |
