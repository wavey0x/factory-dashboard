# Configuration

## Precedence

Tidal loads settings in this order:

```text
environment variables > ~/.tidal/config.yaml > Python defaults
```

Secrets belong in `~/.tidal/.env`. Operational knobs belong in `~/.tidal/config.yaml`.

## Files

| File | Purpose |
|---|---|
| `~/.tidal/config.yaml` | Runtime settings for scanner, API, multicall, pricing, and transaction behavior |
| `~/.tidal/.env` | Secrets such as `RPC_URL`, API keys, and keystore secrets |
| `~/.tidal/kick.yaml` | Kick pricing, token caps, ignore rules, and cooldown policy for the runtime executing prepare logic |

## Role Model

Tidal uses one runtime config format, but not every key matters to every user:

- `CLI client`: runs `tidal`, calls the API, and may sign/broadcast locally.
- `Server operator`: runs `tidal-server`, owns scans, SQLite, API serving, and reconciliation.

The generated scaffold in `~/.tidal/config.yaml` is ordered for the common CLI-client case:

- `CLI client defaults`
- `Shared execution defaults`
- `Shared runtime`
- `Server operator only`

## `~/.tidal/.env`

Common environment variables:

- CLI client:
  `TIDAL_API_KEY`, `TXN_KEYSTORE_PATH`, `TXN_KEYSTORE_PASSPHRASE`
- Server operator:
  `RPC_URL`, `TOKEN_PRICE_AGG_KEY`
- Either role when useful:
  `TIDAL_API_BASE_URL`, `TIDAL_API_HOST`, `TIDAL_API_PORT`

Less common but supported:

- `DB_PATH`
- `CHAIN_ID`
- any setting declared in `tidal/config.py`

## `~/.tidal/config.yaml`

Run `tidal init` to scaffold the default files under `~/.tidal/`. The generated `config.yaml` is the best starting point.

### CLI client defaults

These are at the top of the scaffold because the CLI client is the common case:

- `tidal_api_base_url`
- `tidal_api_request_timeout_seconds`

### Shared execution defaults

These affect local execution and server-side transaction logic:

- `auction_kicker_address`
- `txn_usd_threshold`
- `txn_max_base_fee_gwei`
- `txn_max_priority_fee_gwei`
- `txn_max_gas_limit`
- `txn_start_price_buffer_bps`
- `txn_min_price_buffer_bps`
- `txn_quote_spot_warning_threshold_pct`
- `txn_max_data_age_seconds`
- `prepared_action_max_age_seconds`
- `txn_require_curve_quote`
- `max_batch_kick_size`
- `batch_kick_delay_seconds`

`prepared_action_max_age_seconds` is a CLI-side safety guard for API-backed broadcast flows. If the operator waits too long between prepare and send, the client skips that prepared transaction and tells the user to re-run so quotes are refreshed.

### Shared runtime

Used by both roles, or by any command that needs local RPC access:

- `db_path`
- `chain_id`
- `rpc_timeout_seconds`
- `rpc_retry_attempts`

### Server operator only

These drive scanning, cached state, discovery, and API serving:

- `scan_interval_seconds`
- `scan_concurrency`
- `scan_auto_settle_enabled`
- `monitored_fee_burners`
- `multicall_enabled`
- `multicall_address`
- `multicall_discovery_batch_calls`
- `multicall_rewards_batch_calls`
- `multicall_rewards_index_max`
- `multicall_balance_batch_calls`
- `multicall_overflow_queue_max`
- `multicall_auction_batch_calls`
- `auction_factory_address`
- `price_refresh_enabled`
- `token_price_agg_base_url`
- `price_timeout_seconds`
- `price_retry_attempts`
- `price_concurrency`
- `price_delay_seconds`
- `auctionscan_base_url`
- `auctionscan_api_base_url`
- `auctionscan_recheck_seconds`
- `tidal_api_host`
- `tidal_api_port`
- `tidal_api_receipt_reconcile_interval_seconds`
- `tidal_api_receipt_reconcile_threshold_seconds`
- `tidal_api_cors_allowed_origins`

## `monitored_fee_burners`

`config.yaml` stores fee burners as a list:

```yaml
monitored_fee_burners:
  - address: "0x..."
    want_address: "0x..."
    label: "Human name"
```

These entries are used by the scanner to:

- load fee-burner balances
- resolve source names
- map fee burners to auctions using `(receiver, want)`

## `~/.tidal/kick.yaml`

This file controls four things:

1. auction pricing profiles
2. token-specific USD sizing caps
3. manual ignore rules
4. cooldown policy

Runtime boundary:

- for API-backed `tidal` commands, the server's `kick.yaml` is authoritative
- a workstation's local `~/.tidal/kick.yaml` does not affect kick prepare results returned by a remote API
- local `kick.yaml` matters when this machine is running `tidal-server` or other local transaction-service execution

### Pricing profiles

```yaml
default_profile: volatile

profiles:
  volatile:
    start_price_buffer_bps: 1000
    min_price_buffer_bps: 500
    step_decay_rate_bps: 50

  stable:
    start_price_buffer_bps: 100
    min_price_buffer_bps: 50
    step_decay_rate_bps: 2
```

### Profile overrides

```yaml
profile_overrides:
  - auction: "0xAuction"
    token: "0xSellToken"
    profile: stable
```

Anything not listed falls back to `default_profile`.

### USD kick caps

Limit how much USD value of a specific sell token is used in one kick:

```yaml
usd_kick_limit:
  "0xToken": 10000
```

This cap is applied after the live source balance is read and before the live quote is requested.

### Ignore rules

Use `ignore` to skip specific sources, auctions, or auction/token combinations:

```yaml
ignore:
  - source: "0xSource"
  - auction: "0xAuction"
  - auction: "0xAuction"
    token: "0xSellToken"
```

Ignored candidates are removed before same-auction ranking.

### Cooldown policy

Use `cooldown_minutes` for the global default, and `cooldown` for per-auction/token overrides:

```yaml
cooldown_minutes: 60

cooldown:
  - auction: "0xAuction"
    token: "0xSellToken"
    minutes: 180
```

Cooldown applies to the `(auction, token)` pair, not to the whole auction or whole source.

## Important Defaults

Current defaults from `tidal/config.py` include:

- `scan_interval_seconds = 300`
- `rpc_timeout_seconds = 10`
- `price_timeout_seconds = 10`
- `txn_usd_threshold = 100`
- `txn_max_base_fee_gwei = 0.5`
- `txn_max_priority_fee_gwei = 2`
- `txn_quote_spot_warning_threshold_pct = 2`
- `prepared_action_max_age_seconds = 300`
- `cooldown_minutes = 60` in `kick.yaml`
- `tidal_api_request_timeout_seconds = 30`

## Rule Of Thumb

- run `tidal init`
- put secrets in `~/.tidal/.env`
- put operational settings in `~/.tidal/config.yaml`
- if you use hosted or remote API-backed `tidal`, treat server-side `kick.yaml` as the source of truth
- edit local `~/.tidal/kick.yaml` only when this machine owns the execution runtime
