# Server Operator CLI Overview

`tidal-server` is the server operator CLI. It owns the shared database, runs the scanner and API, and can optionally execute transactions from the server host itself.

Use it on the machine that owns:

- the canonical SQLite database
- the scanner daemon
- the API process
- any server-side broadcast wallet

## Default Runtime Files

By default, `tidal-server` reads:

- `~/.tidal/config.yaml`
- `~/.tidal/.env`
- `~/.tidal/auction_pricing_policy.yaml`

That is the same runtime home used by `tidal`.

## Top-Level Commands

| Command | Use it when | Reference |
|---|---|---|
| `db` | You need to apply migrations | [Server Operator: `tidal-server db`](cli-server-db.md) |
| `scan` | You need to run one scan or the scanner daemon | [Server Operator: `tidal-server scan`](cli-server-scan.md) |
| `api` | You need to serve the FastAPI control plane | [Server Operator: `tidal-server api`](cli-server-api.md) |
| `auth` | You need to create, list, or revoke API keys | [Server Operator: `tidal-server auth`](cli-server-auth.md) |
| `kick` | You want to inspect or execute kicks directly from the server | [Server Operator: `tidal-server kick`](cli-server-kick.md) |
| `auction` | You want to manage auctions directly from the server | [Server Operator: `tidal-server auction`](cli-server-auction.md) |
| `logs` | You want local operational history from the shared database | [Server Operator: `tidal-server logs`](cli-server-logs.md) |

## When Not To Use `tidal-server`

Do not use `tidal-server` from a random workstation just because it has more commands. For normal remote operation against a hosted control plane, use the lighter CLI client [`tidal`](cli-client-reference.md).
