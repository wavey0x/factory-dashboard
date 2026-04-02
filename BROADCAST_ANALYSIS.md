# Broadcast Flag Analysis

## Decision

Adopt a simpler CLI model:

- remove user-facing `--broadcast`
- do not add user-facing `--dry-run`
- mutating one-shot commands are live by default
- a confirmation checkpoint is required before any send
- `--no-confirmation` is the only bypass for automated / non-interactive sending
- keep read-only behavior in separate read-only commands like `inspect`

This is the cleanest model for Tidal.

## Why

The current `--broadcast` model makes command meaning too dependent on an easy-to-forget flag.

Examples:

- `tidal kick inspect` already exists as the read-only shortlist command
- `tidal kick run` without `--broadcast` behaves more like another inspect path
- `tidal kick run --broadcast` is the path that actually prepares and sends

That is awkward.

From first principles:

- `inspect` should inspect
- `run` should run
- `deploy` should deploy
- `enable-tokens` should enable tokens
- `settle` should settle

The command verb should describe the default behavior.

## Scope

### One-shot mutating commands

These become live by default:

- `tidal kick run`
- `tidal-server kick run`
- `tidal auction deploy`
- `tidal auction enable-tokens`
- `tidal auction settle`
- `tidal-server auction deploy`
- `tidal-server auction enable-tokens`
- `tidal-server auction settle`

### Read-only commands

These remain explicit read-only commands:

- `tidal kick inspect`
- `tidal-server kick inspect`
- any future watch-style or inspect-style commands

### Background / unattended commands

These do not get a separate preview mode.

Instead:

- they remain live in concept
- but they require `--no-confirmation` before they are allowed to run unattended

That applies to:

- `tidal-server kick daemon`
- scanner commands when `scan_auto_settle_enabled` can cause on-chain sends

## Runtime semantics

### One-shot mutating commands

Default flow:

1. resolve signer / sender
2. prepare the action
3. simulate / estimate gas
4. render the review panel
5. prompt for confirmation
6. send if confirmed

If the user answers `no`, the command exits without sending.

### `--no-confirmation`

`--no-confirmation` means:

- skip the final checkpoint
- proceed directly to send once prepare / simulation succeeds

It does **not** disable internal simulation or warning generation.

### No separate dry-run mode

User-facing preview-only mode is removed for mutating commands.

The preview still exists internally and is shown before the confirmation checkpoint.

If a user wants read-only behavior, they should use an explicit read-only command such as `kick inspect`.

## Important implementation caveat: `--json`

For live-by-default mutating commands, `--json` cannot coexist cleanly with an interactive confirmation prompt.

Implementation rule:

- mutating commands with `--json` must require `--no-confirmation`

Reason:

- otherwise prompt text will interfere with machine-readable output

So the allowed patterns become:

- `tidal kick run` → interactive live flow
- `tidal kick run --no-confirmation` → unattended live flow
- `tidal kick run --json --no-confirmation` → machine-readable unattended live flow

And disallowed:

- `tidal kick run --json`

That should fail with a clear error telling the user that `--json` on mutating commands requires `--no-confirmation`.

## Background command rule

### `tidal-server kick daemon`

Do not invent a separate `--execute` / observe mode.

Keep the model simple:

- `tidal-server kick daemon --no-confirmation` = allowed
- `tidal-server kick daemon` = refuse to run

Reason:

- daemon mode is fundamentally unattended
- a per-transaction prompt loop is poor UX and operationally weak
- keeping one bypass flag is simpler than introducing a second live/observe mode

### Scanner auto-settle

If `scan_auto_settle_enabled` is true and the scanner may send transactions:

- `tidal-server scan run` and `tidal-server scan daemon` must require `--no-confirmation`

No interactive confirmation path is needed for scanner auto-settle in this pass.
It should be treated as an unattended transaction path.

## Concrete implementation plan

### 1. Replace the option surface

In `tidal/cli_options.py`:

- remove `BroadcastOption`
- replace `BypassConfirmationOption` with `NoConfirmationOption`
- primary flag name should be `--no-confirmation`

Optional short-term compatibility:

- keep `--bypass-confirmation` as a hidden deprecated alias for one release

### 2. Update one-shot server CLIs

In:

- `tidal/kick_cli.py`
- `tidal/auction_cli.py`

Change one-shot mutating commands so they:

- always resolve execution with signing required
- always prepare and simulate
- always render the review panel
- prompt unless `--no-confirmation` is set
- no longer branch on `broadcast`

Remove all “Dry run only. No transaction was sent.” messaging from these commands.

### 3. Update one-shot API-backed CLIs

In:

- `tidal/operator_kick_cli.py`
- `tidal/operator_auction_cli.py`

Change one-shot mutating commands so they:

- always require authenticated API access
- always resolve execution with signing required
- always call prepare endpoints, not inspect-like preview fallbacks
- prompt unless `--no-confirmation` is set
- no longer branch on `broadcast`

For `tidal kick run` specifically:

- keep `tidal kick inspect` as the read-only shortlist command
- remove the current non-broadcast inspect-like path from `run`

### 4. Update daemon / unattended commands

In:

- `tidal/kick_cli.py`
- `tidal/scan_cli.py`

Rules:

- `kick daemon` must require `--no-confirmation`
- `scan run` / `scan daemon` must require `--no-confirmation` when `scan_auto_settle_enabled` is true

Implementation can reuse existing runtime behavior; no separate preview mode is needed.

### 5. Update execution resolution

In `tidal/cli_context.py`:

- remove the `broadcast`-driven meaning from `resolve_execution`
- keep the lower-level concept of `required` signer resolution

At the call sites:

- one-shot mutating commands pass `required=True`
- unattended commands pass `required=True`
- read-only commands do not resolve execution

### 6. Update help text and status text

Remove wording that assumes `--broadcast`, such as:

- “Use --broadcast to submit transaction on chain.”
- “broadcast kick execution”
- “broadcast settlement execution”

Replace with wording that matches the new model:

- “Confirmation required unless --no-confirmation is provided.”
- “This command sends transactions after confirmation.”

### 7. Keep internal simulation

Do **not** remove:

- prepare endpoints
- gas estimation
- revert detection
- warning generation
- pre-send stale checks

The change is CLI mode semantics, not safety behavior.

## Documentation changes

Update:

- `README.md`
- `docs/cli-reference.md`
- `docs/cli-client-kick.md`
- `docs/cli-client-auction.md`
- `docs/cli-server-kick.md`
- `docs/cli-server-auction.md`
- `docs/operator-guide.md`
- `docs/server-ops.md`

New documented contract:

- one-shot mutating commands send by default after confirmation
- `--no-confirmation` is required for unattended or machine-readable mutation
- `inspect` is the explicit read-only path

## Test updates

Update unit and integration coverage in:

- `tests/integration/test_cli_integration.py`
- `tests/unit/test_operator_kick_cli.py`
- `tests/unit/test_operator_auction_cli.py`
- `tests/unit/test_cli.py`

Add coverage for:

- mutating one-shot commands no longer require `--broadcast`
- one-shot commands prompt by default
- `--no-confirmation` skips prompt
- `--json` without `--no-confirmation` fails on mutating commands
- `kick daemon` requires `--no-confirmation`
- `scan run` / `scan daemon` require `--no-confirmation` when auto-settle is enabled

## Migration strategy

### Phase 1

Implement the new behavior and add `--no-confirmation`.

Optionally keep `--broadcast` as a hidden deprecated alias for one short transition window if needed.

### Phase 2

Remove `--broadcast` from help text, docs, and tests.

### Phase 3

Remove deprecated parsing support entirely.

## Final recommendation

The right model for Tidal is:

- no `--broadcast`
- no user-facing `--dry-run`
- one-shot mutating commands are live by default
- confirmation is required by default
- `--no-confirmation` is the single explicit bypass
- read-only behavior stays in explicit read-only commands

This is the simplest and clearest model with the fewest modes.
