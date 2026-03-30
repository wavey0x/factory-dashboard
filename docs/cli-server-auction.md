# Server Operator: `tidal-server auction`

`tidal-server auction` manages auctions directly from the server host instead of going through the API-backed client flow.

## Subcommands

- `deploy`
- `enable-tokens`
- `settle`

## Common Invocations

Deploy a new auction:

```bash
tidal-server auction deploy \
  --want 0xWant \
  --receiver 0xReceiver \
  --starting-price 1234 \
  --broadcast \
  --sender 0xYourAddress \
  --account wavey3
```

Enable tokens:

```bash
tidal-server auction enable-tokens 0xAuction --broadcast --sender 0xYourAddress --account wavey3
```

Settle the current lot:

```bash
tidal-server auction settle 0xAuction --broadcast --sender 0xYourAddress --account wavey3
```

## Important Flags

Shared across these subcommands:

- `--broadcast`
- `--bypass-confirmation`
- `--sender`
- `--account`
- `--keystore`
- `--password-file`
- `--json`

Subcommand-specific flags:

- `deploy`: `--want`, `--receiver`, `--starting-price`, optional factory and governance overrides
- `enable-tokens`: `--extra-token`
- `settle`: `--token`, `--sweep`, `--receipt-timeout`

## Notes

These commands execute locally against the configured RPC and shared database. They are operational tools for the server operator, not the normal remote-client path.
