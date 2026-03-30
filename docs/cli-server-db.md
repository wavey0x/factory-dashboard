# Server Operator: `tidal-server db`

`tidal-server db` is the database maintenance entry point.

## Subcommands

- `migrate`: apply the current Alembic schema migrations

## Common Invocation

```bash
tidal-server db migrate
```

## When To Run It

Run migrations:

- during first-time bootstrap
- after upgrading the installed package
- as an `ExecStartPre=` step before API or scanner startup

## Notes

- `migrate` is safe to run repeatedly.
- It does not require `RPC_URL`.
- It operates on the database path resolved from `~/.tidal/config.yaml` and any `TIDAL_*` path overrides.
