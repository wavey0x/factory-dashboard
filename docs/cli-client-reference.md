# CLI Client Overview

`tidal` is the API-backed CLI client. It asks the control-plane API to inspect and prepare work, then signs and broadcasts locally.

Use it when you want:

- remote access to the shared scanner state
- local wallet custody
- a lighter operational footprint than running the full server

## Default Runtime Files

By default, `tidal` reads:

- `~/.tidal/config.yaml`
- `~/.tidal/.env`
- `~/.tidal/auction_pricing_policy.yaml`

If those files do not exist yet, run:

```bash
tidal init
```

## Top-Level Commands

| Command | Use it when | Reference |
|---|---|---|
| `init` | You are bootstrapping a workstation or refreshing scaffold files | [CLI Client: `tidal init`](cli-client-init.md) |
| `kick` | You want to inspect or broadcast kick candidates through the API | [CLI Client: `tidal kick`](cli-client-kick.md) |
| `auction` | You want to deploy, enable, or settle auctions through the API | [CLI Client: `tidal auction`](cli-client-auction.md) |
| `logs` | You want historical kick and scan data from the API | [CLI Client: `tidal logs`](cli-client-logs.md) |

## Shared Client Options

API-backed client commands commonly accept:

- `--config`
- `--api-base-url`
- `--api-key`

Broadcasting commands also share the wallet flags documented in the [CLI Reference overview](cli-reference.md).

## When Not To Use `tidal`

Do not use `tidal` for:

- database migrations
- scanner daemon management
- API serving
- API key creation or revocation

Those live under [`tidal-server`](cli-server-reference.md).
