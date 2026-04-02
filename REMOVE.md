# Remove `--account` And `--sender`

## Goal

Remove `--account` and `--sender` from the user-facing CLI and related docs/config guidance.

Execution should become keystore-driven:

- prefer `TXN_KEYSTORE_PATH` and `TXN_KEYSTORE_PASSPHRASE`
- allow explicit `--keystore` and `--password-file`
- infer the sender address from the resolved signer or keystore

## Scope

This change applies to:

- server mutating commands
- client mutating commands
- shared CLI option helpers
- execution-resolution helpers
- docs and examples
- tests

This does **not** necessarily remove internal `sender` fields from prepared-action payloads or audit records.
Transactions still need a sender address; the change is that the CLI no longer asks the operator to provide it explicitly.

## Planned Changes

1. Remove `AccountOption` and `SenderOption` from shared CLI option definitions.
2. Simplify shared execution resolution so it no longer accepts `account_name` or explicit `sender`.
3. Update mutating CLI commands to resolve execution from:
   - configured keystore env
   - `--keystore`
   - `--password-file`
4. Keep inferred sender behavior by deriving it from the signer or resolved keystore.
5. Remove user-facing docs, examples, and config references to `--account` and `--sender`.
6. Update tests to reflect keystore/config-driven execution only.

## Expected Behavioral Changes

- `tidal kick run --sender ... --account ...` stops existing.
- `tidal-server kick run --sender ... --account ...` stops existing.
- auction mutation commands stop accepting those flags too.
- unattended systemd examples become simpler because only keystore env/config is required.

## Risks

- This is a breaking CLI change for any existing scripts or operator habits using those flags.
- Some client/operator flows currently rely on Foundry keystore-name convenience via `--account`.
- API-backed operator commands still need correct sender inference when preparing and broadcasting actions.

## Validation

After implementation:

- `--help` output no longer shows `--account` or `--sender`
- mutating commands still work with `TXN_KEYSTORE_PATH` and `TXN_KEYSTORE_PASSPHRASE`
- explicit `--keystore` and `--password-file` still work
- focused CLI and helper tests pass
