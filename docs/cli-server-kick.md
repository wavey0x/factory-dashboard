# Server Operator: `tidal-server kick`

`tidal-server kick` evaluates and optionally executes kick candidates directly on the server host.

## Subcommands

- `inspect`: explain why candidates are ready, skipped, or deferred
- `run`: evaluate candidates once and send transactions after review
- `daemon`: loop continuously and evaluate on an interval

## Common Invocations

Inspect the current shortlist:

```bash
tidal-server kick inspect
```

Run one evaluation pass with explanations:

```bash
tidal-server kick run --explain
```

Run interactively from the server host:

```bash
tidal-server kick run --sender 0xYourAddress --account wavey3
```

Run continuously:

```bash
tidal-server kick daemon --no-confirmation --interval-seconds 300 --sender 0xYourAddress --account wavey3
```

## Important Flags

- `--source-type`
- `--source`
- `--auction`
- `--limit`
- `--no-confirmation`
- `--verbose`
- `--explain`
- `--require-curve-quote` and `--allow-missing-curve-quote`
- `--json` on `run` requires `--no-confirmation`

The `run` and `daemon` subcommands also use the shared wallet flags:

- `--sender`
- `--account`
- `--keystore`
- `--password-file`

## When To Use This Instead Of `tidal kick`

Use `tidal-server kick` when:

- the server itself owns the execution wallet
- you want a server-local daemonized kicker
- you are debugging shortlist behavior directly against the shared database

For remote human-operated execution against the control plane, prefer [`tidal kick`](cli-client-kick.md).
