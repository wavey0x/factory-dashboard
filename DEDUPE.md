# CLI Dedupe Plan

## Goal

Make `tidal` the only operator CLI.
Make `tidal-server` the runtime and host-admin CLI.

The target is a single operator path with no fallback command surface:

- operator actions go through `tidal`
- runtime ownership stays in `tidal-server`

## Principles

- Remove duplication completely. Do not deprecate.
- Do not add aliases, forwarding commands, warnings, feature flags, or compatibility shims.
- Prefer deleting old code over wrapping it.
- Keep one operator story:
  - prepare through the API
  - sign locally
  - broadcast locally
  - report audit data back to the API
- If an operator wants to act from the server host, they still use `tidal`, pointed at the local API.

## Final CLI Surface

`tidal` keeps:

- `init`
- `kick`
- `auction`
- `logs`

`tidal-server` keeps:

- `init-config`
- `db`
- `scan`
- `api`
- `auth`

`tidal-server` removes:

- `kick`
- `auction`
- `logs`

## Important Boundary

`tidal-server scan run --auto-settle` stays.

That is not an operator command surface. It is part of server runtime automation.
This dedupe work is about removing duplicate operator entrypoints, not removing runtime-owned scanning behavior.

## What Gets Deleted

Delete the direct server-side operator command modules:

- `tidal/kick_cli.py`
- `tidal/auction_cli.py`
- `tidal/logs_cli.py`

Delete the `tidal-server` mounts for those command groups from:

- `tidal/server_cli.py`

Delete docs and examples for:

- `tidal-server kick ...`
- `tidal-server auction ...`
- `tidal-server logs ...`

Delete tests that exist only to preserve those removed command surfaces.

## Canonical Operator Path

All operator actions become API-backed:

- `tidal kick inspect`
- `tidal kick run`
- `tidal auction deploy`
- `tidal auction enable-tokens`
- `tidal auction settle`
- `tidal logs ...`

If someone wants to run those from the server host, the answer is still:

- run `tidal`
- point it at `http://127.0.0.1:8787`
- provide a valid API key
- provide the local keystore config

No new “server-local operator mode” should be added.

## Internal Cleanup

After removing the duplicate server command modules, rename the surviving operator CLI modules to the canonical names in one direct pass:

- `tidal/operator_kick_cli.py` -> `tidal/kick_cli.py`
- `tidal/operator_auction_cli.py` -> `tidal/auction_cli.py`
- `tidal/operator_logs_cli.py` -> `tidal/logs_cli.py`

Then update imports accordingly.

Do not keep wrapper modules behind.
Do not keep temporary re-export files.

The result should be one set of CLI modules, named after the commands they own.

## Docs Simplification

Rewrite docs to tell one clean story:

- `tidal-server` is for server runtime ownership
- `tidal` is for operator reads and writes

That means:

- remove server-side mutation walkthroughs
- remove server-side log-inspection walkthroughs
- remove examples that suggest `tidal-server kick run` is normal
- remove examples that suggest `tidal-server auction ...` is normal

Keep server docs focused on:

- `init-config`
- `db migrate`
- `scan run`
- `api serve`
- `auth`
- systemd / deploy wiring

## What We Should Not Add

Do not add:

- deprecation warnings
- transitional aliases
- hidden compatibility flags
- “legacy mode”
- dual-path docs
- fallback server mutation commands
- extra abstractions whose only purpose is to preserve the old split

The whole point is to make the code and product easier to understand by deleting the second operator path.

## Execution Order

1. Remove `kick`, `auction`, and `logs` from `tidal-server`.
2. Delete the direct server-side CLI modules and tests tied only to them.
3. Rename the surviving operator CLI modules to canonical names.
4. Update imports, docs, and help text to reflect the single operator path.
5. Verify `--help` output for both executables.
6. Verify targeted operator and server tests.

## Acceptance Criteria

- `tidal-server --help` does not show `kick`, `auction`, or `logs`
- `tidal --help` remains the only operator surface
- there is only one implementation path for operator kick commands
- there is only one implementation path for operator auction commands
- there is only one implementation path for operator log commands
- docs describe one operator workflow, not two
- no backward-compat code remains in the tree

## Non-Goals

- Do not redesign the API.
- Do not change scan auto-settle behavior.
- Do not unify unrelated persistence tables just because they are nearby.
- Do not add migration layers for removed commands.

The job is straightforward: remove the duplicate operator surface and leave one clean path.
