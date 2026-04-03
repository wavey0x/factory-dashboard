# Kick Planning Simplification Plan

## Goal

Reduce backend complexity by making the kick path use one first-class plan object from preparation through execution.

The immediate goal is not to redesign the whole system. The goal is to stop rebuilding the same kick workflow in multiple places.

## Why This Is The Right Focus

Today the same kick flow is spread across several layers:

- `tidal/api/services/action_prepare.py` prepares kick actions for the API.
- `tidal/transaction_service/service.py` repeats live-run shortlist, prepare, and execution branching.
- `tidal/operator_cli_support.py` reinterprets dict-shaped prepared transactions for broadcast.
- `tidal/api/services/action_audit.py` persists another dict-shaped representation of the same work.
- `tidal/transaction_service/kicker.py` contains the core chain-facing logic and is forced to support several callers with different expectations.

This creates three problems at once:

1. The same domain logic is duplicated in API prepare and live execution.
2. The system translates kick actions between dataclasses, ad hoc dicts, and persistence rows multiple times.
3. Complexity accumulates in orchestration layers instead of staying in one obvious boundary.

If we fix only one architectural problem right now, this is the one with the highest leverage.

## Decision

Introduce a single concrete `KickPlanner` that produces a typed `KickPlan`.

All kick callers should consume that plan:

- API prepare should build and persist it.
- Live transaction runs should build and execute it.
- CLI broadcast should consume its serialized `TxIntent`s.

The key rule:

`KickPlan` is the only internal representation of a prepared kick action.

Everything else becomes either:

- an input to planning
- execution of the plan
- serialization of the plan

## Non-Goals

These are explicitly out of scope for the first implementation:

- No generic action framework for every action type.
- No plugin system.
- No abstract base class hierarchy for planners or executors.
- No database migration unless we prove the current `preview_json` plus transaction rows are insufficient.
- No scanner refactor in the same branch.
- No UI refactor in the same branch.
- No attempt to rename every service or fully split `AuctionKicker` in the first pass.

This plan is intentionally kick-specific first.

## Simplicity Rules

The implementation should follow these constraints:

- Use one small concrete planner class, not a framework.
- Reuse existing `PreparedKick`, `PreparedSweepAndSettle`, and `KickCandidate` types where they are still good enough.
- Add only the minimum new types needed to make the plan explicit.
- Keep the current API response shape stable in phase 1.
- Keep the current action-audit database shape stable in phase 1.
- Keep deploy, enable-tokens, and settle preparation untouched until the kick pattern is proven.
- Avoid splitting files just because they are large; split only where a clear boundary appears.

## Target Architecture

### 1. Selection Layer

Existing module:

- `tidal/transaction_service/evaluator.py`

Responsibility:

- Read cached shortlist inputs from SQLite.
- Apply threshold, ignore, cooldown, same-auction, and limit rules.
- Return ranked `KickCandidate`s and existing skip metadata.

This layer stays mostly unchanged.

### 2. Planning Layer

New module:

- `tidal/transaction_service/planner.py`

Primary object:

- `KickPlanner`

Responsibility:

- Accept shortlist filters and sender context.
- Build the shortlist using the evaluator.
- Inspect candidate auctions once.
- Ask `AuctionKicker` to prepare each candidate.
- Convert prepared operations into typed transaction intents.
- Estimate gas for those intents.
- Handle batch-to-individual fallback when the batch path is unsendable.
- Return a single `KickPlan`.

What it must not do:

- No DB writes.
- No API action persistence.
- No transaction signing.
- No transaction broadcasting.
- No receipt reconciliation.

### 3. Execution Layer

Existing modules:

- `tidal/transaction_service/service.py`
- `tidal/operator_cli_support.py`

Responsibilities after refactor:

- `TxnService` becomes a thin orchestrator around run lifecycle and server-owned live execution.
- `operator_cli_support` becomes a thin broadcaster for serialized transaction intents.

Execution should consume `TxIntent`s or typed operation wrappers, not rebuild calldata from scratch in multiple places.

### 4. Persistence Layer

Existing module:

- `tidal/api/services/action_audit.py`

Responsibility after refactor:

- Persist a serialized view of `KickPlan`.
- Persist per-transaction rows derived from `KickPlan.tx_intents`.
- Track broadcast and receipt lifecycle exactly as today.

Important first-cut constraint:

- Keep the current DB schema.
- Derive current `preview_json` from `KickPlan.to_preview_payload()`.
- Derive current transaction rows from `KickPlan.to_transaction_payloads()`.

If we later need richer persistence, add it only after the planner is in place and stable.

## Target Internal Data Model

These types should be added to `tidal/transaction_service/types.py` unless they clearly justify a separate file later.

### `TxIntent`

Purpose:

- Represent one unsigned transaction prepared by the planner.

Suggested fields:

- `operation: OperationType`
- `to: str`
- `data: str`
- `value: str = "0x0"`
- `chain_id: int`
- `sender: str | None`
- `gas_estimate: int | None`
- `gas_limit: int | None`

Suggested helpers:

- `to_payload() -> dict[str, object]`
- `from_payload(payload: dict[str, object]) -> TxIntent`

### `PreparedKickOperation`

Purpose:

- Wrap one planned kick plus the transaction that will execute it.

Suggested fields:

- `prepared: PreparedKick`
- `tx_intent: TxIntent`

### `PreparedSweepAndSettleOperation`

Purpose:

- Wrap one planned sweep-and-settle plus the transaction that will execute it.

Suggested fields:

- `prepared: PreparedSweepAndSettle`
- `tx_intent: TxIntent`

### `SkippedPreparedCandidate`

Purpose:

- Represent a candidate that made it past shortlist selection but was skipped during live preparation.

Suggested fields:

- `candidate: KickCandidate`
- `reason: str`

### `KickPlan`

Purpose:

- Be the single internal representation of a prepared kick action.

Suggested fields:

- `source_type: str | None`
- `source_address: str | None`
- `auction_address: str | None`
- `token_address: str | None`
- `limit: int | None`
- `eligible_count: int`
- `selected_count: int`
- `ready_count: int`
- `ignored_skips: list[dict[str, object]]`
- `cooldown_skips: list[dict[str, object]]`
- `deferred_same_auction_count: int`
- `limited_count: int`
- `kick_operations: list[PreparedKickOperation]`
- `sweep_operations: list[PreparedSweepAndSettleOperation]`
- `skipped_during_prepare: list[SkippedPreparedCandidate]`
- `warnings: list[str]`

Suggested helpers:

- `tx_intents() -> list[TxIntent]`
- `prepared_operations_preview() -> list[dict[str, object]]`
- `to_preview_payload() -> dict[str, object]`
- `to_transaction_payloads() -> list[dict[str, object]]`
- `status() -> Literal["ok", "noop"]`

Important note:

- This is intentionally not a generic `ActionPlan`.
- Kick should prove the pattern first.

## Module Responsibilities After Refactor

### `tidal/transaction_service/kicker.py`

Keep:

- candidate inspection
- quote-driven per-candidate preparation
- on-server execution helpers

Add or expose:

- public transaction-intent builders

Suggested public methods:

- `build_single_kick_intent(prepared: PreparedKick, *, sender: str | None) -> TxIntent`
- `build_batch_kick_intent(prepared_items: list[PreparedKick], *, sender: str | None) -> TxIntent`
- `build_sweep_and_settle_intent(prepared: PreparedSweepAndSettle, *, sender: str | None) -> TxIntent`

Remove from outside callers:

- direct use of `_kick_args`
- direct use of `_kick_extended_args`

The rule should be:

Only `AuctionKicker` knows how to turn prepared domain objects into calldata for the `AuctionKicker` contract.

### `tidal/api/services/action_prepare.py`

After refactor, this file should:

- validate inputs
- build `TxnService` or `AuctionKicker` dependencies
- call `KickPlanner.plan(...)`
- persist the result through `create_prepared_action(...)`
- return the serialized plan

It should no longer:

- loop over candidates to prepare them itself
- build batch calldata itself
- reach into `kicker._kick_args`
- own batch fallback policy

### `tidal/transaction_service/service.py`

After refactor, live mode should:

- build a `KickPlan`
- execute its operations
- finalize the run summary

Dry-run mode can stay shortlist-only initially to avoid extra chain calls.

This is an intentional compromise for the first cut:

- live path gets simplified first
- dry-run remains cheap and stable

### `tidal/operator_cli_support.py`

After refactor, this module should:

- accept `TxIntent`s or deserialize them immediately from API payloads
- sign and broadcast them
- report broadcast and receipt outcomes

It should not:

- infer business rules about how kick calldata should be built

## Target Call Flows

### API Prepare

Target flow:

1. route handler validates request
2. `prepare_kick_action(...)` calls `KickPlanner.plan(...)`
3. `KickPlan` is serialized to current preview payload plus transaction payloads
4. `create_prepared_action(...)` persists that serialized data
5. API returns the serialized plan

### CLI Broadcast

Target flow:

1. CLI receives current API response shape
2. CLI deserializes transaction payloads into `TxIntent`s
3. broadcaster signs and sends each intent
4. broadcaster reports tx hash and receipt details back to the API

### Server-Owned Live Run

Target flow:

1. `TxnService.run_once(live=True)` builds a `KickPlan`
2. `TxnService` executes sweep operations and kick operations from that plan
3. `TxnService` updates run counters from plan and execution results
4. `TxnService` finalizes the run

## Detailed Implementation Plan

### Phase 1: Add Plan Types And Serializers

Files:

- `tidal/transaction_service/types.py`
- tests: new `tests/unit/test_kick_plan_types.py`

Changes:

- Add `TxIntent`.
- Add `PreparedKickOperation`.
- Add `PreparedSweepAndSettleOperation`.
- Add `SkippedPreparedCandidate`.
- Add `KickPlan`.
- Add serialization helpers that match the current API payload shape.

Important constraints:

- Do not change the API response shape yet.
- Do not change the DB schema.

Completion check:

- We can create a `KickPlan` in a unit test and serialize it into the exact transaction dict shape used today.

### Phase 2: Expose Public Transaction Builders In `AuctionKicker`

Files:

- `tidal/transaction_service/kicker.py`
- tests: extend `tests/unit/test_txn_kicker.py`

Changes:

- Add public helpers for building single-kick, batch-kick, and sweep-and-settle `TxIntent`s.
- Keep existing private arg builders if needed internally, but stop using them outside the module.

Important constraints:

- No behavioral change to execution.
- No planner yet.

Completion check:

- `action_prepare.py` can build transactions without reaching into private `AuctionKicker` helpers.

### Phase 3: Create `KickPlanner`

Files:

- new `tidal/transaction_service/planner.py`
- tests: new `tests/unit/test_kick_planner.py`

Changes:

- Move kick-specific planning logic out of `action_prepare.py`.
- `KickPlanner.plan(...)` should own:
  - shortlist loading
  - live inspection loading
  - per-candidate preparation
  - conversion of prepare failures into `SkippedPreparedCandidate`
  - gas estimation
  - batch intent generation
  - batch fallback to per-candidate intents on active-auction failures
  - warning collection

The planner should return one `KickPlan` with:

- preview-relevant data
- typed operations
- typed transaction intents
- prepare-time skips
- warnings

Important constraints:

- Keep warning text identical where possible.
- Keep the current preview payload shape identical where possible.

Completion check:

- Existing `test_action_prepare.py` kick cases can be moved or mirrored into `test_kick_planner.py`.

### Phase 4: Make `prepare_kick_action` A Thin Adapter

Files:

- `tidal/api/services/action_prepare.py`
- tests: slim down `tests/unit/test_action_prepare.py`

Changes:

- Replace the large in-function planning block with:
  - build planner dependencies
  - `plan = await planner.plan(...)`
  - persist plan through `create_prepared_action(...)`
  - return serialized plan

What should remain in this function:

- request argument normalization
- API-level error shaping
- persistence call

What should disappear from this function:

- candidate preparation loop
- direct calldata building
- batch fallback logic
- transaction estimation branching

Completion check:

- `prepare_kick_action(...)` becomes mostly orchestration and serialization.

### Phase 5: Make Live `TxnService` Use `KickPlan`

Files:

- `tidal/transaction_service/service.py`
- tests: `tests/integration/test_txn_service.py`, `tests/unit/test_txn_kicker.py`, possibly a new `tests/unit/test_txn_service_planning.py`

Changes:

- In `live=True` mode, replace in-method preparation branching with a planner call.
- Use `KickPlan` to determine:
  - attempts
  - skipped prepare results
  - execution order
  - success and failure aggregation

Keep this simplification boundary:

- live mode uses planner
- dry-run mode remains shortlist-only until the live path is stable

Why this split is acceptable:

- dry-run is intentionally cheap and cache-only
- live mode is where the duplicated complexity currently hurts

Completion check:

- `TxnService._run(...)` no longer duplicates the API prepare candidate classification logic.

### Phase 6: Make CLI Broadcast Use `TxIntent`

Files:

- `tidal/operator_cli_support.py`
- `tidal/kick_cli.py`
- tests: `tests/unit/test_kick_cli.py`

Changes:

- Deserialize transaction payloads into `TxIntent` objects as soon as the API response is received.
- Update `broadcast_prepared_action(...)` to consume `TxIntent`s.
- Keep API wire format unchanged; convert at the edge.

Important constraints:

- Do not change the public HTTP response shape in this phase.
- Do not rewrite action audit reporting.

Completion check:

- CLI broadcast code no longer manipulates anonymous transaction dicts directly after the API boundary.

### Phase 7: Cleanup And Enforce Boundaries

Files:

- `tidal/api/services/action_prepare.py`
- `tidal/transaction_service/service.py`
- `tidal/transaction_service/kicker.py`

Changes:

- Delete now-unused planning helpers from `action_prepare.py`.
- Remove remaining cross-layer private-helper usage.
- Make naming reflect the new boundary if a rename is obviously justified.

Possible follow-up cleanup:

- Split `TxnService` into a run-lifecycle shell plus smaller execution helpers only if the code still reads poorly after the planner lands.

Completion check:

- There is exactly one place where the kick plan is built.

## Testing Plan

### New Tests

- `tests/unit/test_kick_plan_types.py`
- `tests/unit/test_kick_planner.py`

### Existing Tests To Keep Passing

- `tests/unit/test_action_prepare.py`
- `tests/unit/test_kick_cli.py`
- `tests/unit/test_txn_kicker.py`
- `tests/integration/test_txn_service.py`
- `tests/integration/test_api_control_plane.py`

### High-Value Assertions

- Planner returns the same `preparedOperations` preview content as today.
- Planner returns the same `transactions` payload shape as today.
- Batch kick fallback behavior remains unchanged.
- Extended-kick recovery fallback remains unchanged.
- Prepare-time skips remain visible in the same API fields.
- CLI can still broadcast prepared actions without any wire-format change.

## Acceptance Criteria

This effort is successful when all of these are true:

- `prepare_kick_action(...)` is thin and does not own kick planning logic.
- `TxnService` live mode does not duplicate prepare-time branching from the API layer.
- `operator_cli_support` operates on `TxIntent`s, not anonymous dicts past the API boundary.
- No external module reaches into `AuctionKicker` private calldata helpers.
- Existing kick API response shape remains stable.
- Existing action-audit schema remains stable.
- Tests show parity for prepare-time warnings, skips, and transaction payloads.

## Things To Avoid While Implementing

- Do not generalize this into a universal planner system for every action type.
- Do not add a second persistence format before proving the current one is insufficient.
- Do not refactor deploy, enable-tokens, and settle in parallel.
- Do not split `AuctionKicker` into several classes before the planner is established.
- Do not change API payload shape and internal architecture at the same time.

## Follow-Up Work After This Lands

Once the kick planner pattern is stable, the next likely wins are:

- apply the same plan/intention pattern to deploy, enable-tokens, and settle actions
- optionally add richer persisted plan JSON if audit consumers need it
- then revisit `AuctionKicker` and split pure planning helpers from live execution helpers

That order matters.

The planner boundary should come first.
