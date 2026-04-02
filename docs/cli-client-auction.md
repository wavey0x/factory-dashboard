# CLI Client: `tidal auction`

`tidal auction` prepares and sends direct auction-management actions through the API.

## Subcommands

- `deploy`: create a new auction from the configured factory
- `enable-tokens`: queue token enable calls for an auction
- `settle`: resolve an active lot when it is settleable

## Common Invocations

Deploy a new auction:

```bash
tidal auction deploy \
  --want 0xWant \
  --receiver 0xReceiver \
  --starting-price 1234
```

Enable discovered tokens for an auction:

```bash
tidal auction enable-tokens 0xAuction
```

Add one extra token explicitly:

```bash
tidal auction enable-tokens 0xAuction --extra-token 0xToken
```

Settle an auction:

```bash
tidal auction settle 0xAuction
tidal auction settle 0xAuction --token 0xActiveToken
tidal auction settle 0xAuction --sweep
```

Send one of those actions:

```bash
tidal auction settle 0xAuction
```

## Important Flags

Shared across the mutating auction commands:

- `--no-confirmation`
- `--keystore`
- `--password-file`
- `--json` which requires `--no-confirmation`

Subcommand-specific flags:

- `deploy`: `--want`, `--receiver`, `--starting-price`, optional factory and governance overrides
- `enable-tokens`: `--extra-token`
- `settle`: `--token`, `--sweep`

## Behavior Notes

These commands use the same prepare and audit model as `tidal kick`:

1. the API prepares the action and records an audit row
2. the CLI client shows a review panel
3. the CLI client signs and sends locally
4. the CLI client reports the broadcast and receipt back to the API

That means the API owns the action history while the CLI client keeps local control of the wallet.
The signer comes from `TXN_KEYSTORE_PATH` and `TXN_KEYSTORE_PASSPHRASE` by default, or from `--keystore` and `--password-file` if you override them for one command. The sender address is inferred from the resolved keystore.
