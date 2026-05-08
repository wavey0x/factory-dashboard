# Server Operator: `tidal-server scan`

`tidal-server scan` is the discovery and state-refresh surface for the server operator.

## Subcommands

- `run`: execute one scan cycle

## Common Invocations

Run one scan immediately:

```bash
tidal-server scan run --config config/server.yaml
```

Run one scan with auto-settle enabled:

```bash
tidal-server scan run --config config/server.yaml --auto-settle --no-confirmation
```

Run one scan with token auto-enable enabled:

```bash
tidal-server scan run --config config/server.yaml --auto-enable-tokens --no-confirmation
```

Run the full auction maintenance pass:

```bash
tidal-server scan run --config config/server.yaml --auto-settle --auto-enable-tokens --no-confirmation
```

Emit machine-readable output:

```bash
tidal-server scan run --config config/server.yaml --json
```

## Required Inputs

At minimum, scanner execution needs:

- `RPC_URL` in `~/.tidal/server/.env` or `TIDAL_ENV_FILE`
- monitored fee burners in `config/server.yaml`

The scanner populates the shared SQLite cache that powers:

- the dashboard
- kick inspection
- kick preparation
- log history

## Important Config

Common server operator settings for this command:

- `auction_factory_address`
- `monitored_fee_burners`

Most scanner tuning, including `SCAN_CONCURRENCY` and `RPC_TIMEOUT_SECONDS`, now defaults in code. Override it through environment variables only when you are deliberately tuning a deployment.

## Auction Automation Note

Auto-settle and token auto-enable are not configured in `server.yaml`.
They are enabled only when `--auto-settle` or `--auto-enable-tokens` is passed on `scan run`.

When either flag is used, the server also needs valid local wallet configuration such as:

- `TXN_KEYSTORE_PATH`
- `TXN_KEYSTORE_PASSPHRASE`
- `--no-confirmation`

Without those, the scan will fail before it reaches the transaction path.
