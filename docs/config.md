# Configuration

## Precedence

Tidal loads settings in this order:

```text
environment variables > config.yaml > Python defaults
```

Secrets belong in `.env`. Operational knobs belong in `config.yaml`.

## Files

| File | Purpose |
|---|---|
| `config.yaml` | Runtime settings for scanner, API, multicall, pricing, and transaction behavior |
| `.env` | Secrets such as `RPC_URL`, API keys, and keystore secrets |
| `auction_pricing_policy.yaml` | Auction pricing profiles and token-specific USD sizing caps |

## `.env`

Common environment variables:

- `RPC_URL`
- `TOKEN_PRICE_AGG_KEY`
- `TIDAL_API_KEY`
- `TIDAL_API_BASE_URL`
- `TIDAL_API_HOST`
- `TIDAL_API_PORT`

Less common but supported:

- `DB_PATH`
- `CHAIN_ID`
- any setting declared in `tidal/config.py`

## `config.yaml`

The sample file at repo root is the best starting point. Major sections:

### General

- `db_path`
- `chain_id`

### Scanner

- `scan_interval_seconds`
- `scan_concurrency`
- `scan_auto_settle_enabled`
- `rpc_timeout_seconds`
- `rpc_retry_attempts`
- `monitored_fee_burners`

### Multicall

- `multicall_enabled`
- `multicall_address`
- `multicall_discovery_batch_calls`
- `multicall_rewards_batch_calls`
- `multicall_rewards_index_max`
- `multicall_balance_batch_calls`
- `multicall_overflow_queue_max`
- `multicall_auction_batch_calls`

### Auctions

- `auction_factory_address`

### Pricing

- `price_refresh_enabled`
- `token_price_agg_base_url`
- `price_timeout_seconds`
- `price_retry_attempts`
- `price_concurrency`
- `price_delay_seconds`
- `auctionscan_base_url`
- `auctionscan_api_base_url`
- `auctionscan_recheck_seconds`

### Transaction service

- `auction_kicker_address`
- `txn_usd_threshold`
- `txn_max_base_fee_gwei`
- `txn_max_priority_fee_gwei`
- `txn_max_gas_limit`
- `txn_start_price_buffer_bps`
- `txn_min_price_buffer_bps`
- `txn_quote_spot_warning_threshold_pct`
- `txn_max_data_age_seconds`
- `txn_cooldown_seconds`
- `txn_require_curve_quote`
- `max_batch_kick_size`
- `batch_kick_delay_seconds`

### API / control plane

- `tidal_api_host`
- `tidal_api_port`
- `tidal_api_request_timeout_seconds`
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

## `auction_pricing_policy.yaml`

This file controls two things:

1. auction pricing profiles
2. token-specific USD sizing caps

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

### Auction overrides

Map `auction -> sell token -> profile`:

```yaml
auctions:
  "0xAuction":
    "0xSellToken": stable
```

Anything not listed falls back to `default_profile`.

### USD kick caps

Limit how much USD value of a specific sell token is used in one kick:

```yaml
usd_kick_limit:
  "0xToken": 10000
```

This cap is applied after the live source balance is read and before the live quote is requested.

## Important Defaults

Current defaults from `tidal/config.py` include:

- `scan_interval_seconds = 300`
- `rpc_timeout_seconds = 10`
- `price_timeout_seconds = 10`
- `txn_usd_threshold = 100`
- `txn_max_base_fee_gwei = 0.5`
- `txn_max_priority_fee_gwei = 2`
- `txn_quote_spot_warning_threshold_pct = 2`
- `txn_cooldown_seconds = 3600`
- `tidal_api_request_timeout_seconds = 30`

## Rule Of Thumb

- put secrets in `.env`
- put operational settings in `config.yaml`
- put pricing intent in `auction_pricing_policy.yaml`
