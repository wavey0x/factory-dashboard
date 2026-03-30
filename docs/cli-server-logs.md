# Server Operator: `tidal-server logs`

`tidal-server logs` exposes local operational history from the shared database.

## Subcommands

- `kicks`
- `scans`
- `show`

## Common Invocations

Recent kicks:

```bash
tidal-server logs kicks
```

Recent scans:

```bash
tidal-server logs scans
```

Filter kicks by status:

```bash
tidal-server logs kicks --status CONFIRMED
```

Inspect one run in detail:

```bash
tidal-server logs show <run_id>
```

## When To Reach For It

Use these commands while:

- debugging scanner behavior
- confirming recent kick attempts
- checking one run record before opening the dashboard
- exporting history with `--json`
