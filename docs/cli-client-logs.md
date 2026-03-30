# CLI Client: `tidal logs`

`tidal logs` is the read-only history surface for recent kick attempts and scan runs exposed by the API.

## Subcommands

- `kicks`: recent kick attempts
- `scans`: recent scan runs
- `show`: one detailed run record

## Common Invocations

Recent kicks:

```bash
tidal logs kicks
```

Only confirmed kicks:

```bash
tidal logs kicks --status CONFIRMED
```

Filter to one source or auction:

```bash
tidal logs kicks --source 0xSource
tidal logs kicks --auction 0xAuction
```

Recent scan runs:

```bash
tidal logs scans
```

Inspect one historical run:

```bash
tidal logs show <run_id>
```

## Notes

- These commands are safe to use without broadcast credentials.
- `--json` is useful when exporting or post-processing historical data.
- The data comes from the server-side audit tables, not from local CLI state.
