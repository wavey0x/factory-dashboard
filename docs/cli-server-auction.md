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
  --starting-price 1234
```

Enable tokens:

```bash
tidal-server auction enable-tokens 0xAuction
```

Settle the current lot:

```bash
tidal-server auction settle 0xAuction
```

## Important Flags

Shared across these subcommands:

- `--no-confirmation`
- `--keystore`
- `--password-file`
- `--json` which requires `--no-confirmation`

Subcommand-specific flags:

- `deploy`: `--want`, `--receiver`, `--starting-price`, optional factory and governance overrides
- `enable-tokens`: `--extra-token`
- `settle`: `--token`, `--sweep`, `--receipt-timeout`

## Notes

These commands execute locally against the configured RPC and shared database. They are operational tools for the server operator, not the normal remote-client path.
Wallet resolution is keystore-driven: use `TXN_KEYSTORE_PATH` and `TXN_KEYSTORE_PASSPHRASE` by default, or `--keystore` and `--password-file` for a one-off override. The sender address is inferred from the keystore.
