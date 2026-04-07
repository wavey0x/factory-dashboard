# Stale Lot Sweep Fix Plan

## Problem

The current `resolveAuction()` design tries to clean an inactive funded kicked lot with:

1. `sweep(token)`
2. transfer swept balance to `receiver`
3. `disable(token)`
4. `enable(token)`

That is the wrong primitive for some tokens.

Live example:

- auction: `0xA00E6b35C23442fa9D5149Cba5dd94623fFE6693`
- stuck token: `CJPY` (`0x1cfa5641c01406aB8AC350dEd7d735ec41298372`)
- preview state: inactive, `kicked != 0`, balance `> 0`

Observed behavior:

- `sweep(token)` estimates successfully
- `disable(token)` reverts with `Amount is zero.`

So the failure is not stale-lot discovery and not sweep itself. The failure is the reset step.

## Root Cause

`disable()` is not a safe universal reset primitive.

In the verified auction source, `disable()`:

- deletes the auction struct
- revokes relayer approval via `forceApprove(..., 0)`
- removes the token from `enabledAuctions`

That makes stale-lot cleanup depend on token-specific approval behavior. For tokens like `CJPY`, the disable path reverts, so the current `PATH_SWEEP_AND_RESET` and `PATH_RESET_ONLY` model is not reliable.

## Contract Fix

Simplify the resolver state machine and remove `disable -> enable` from the stuck-lot closeout path.

### New Resolution Rules

1. `active && balance > 0`
   - path: `SWEEP_AND_SETTLE`
   - requires `forceLive = true`

2. `active && balance == 0`
   - path: `SETTLE_ONLY`

3. `!active && kicked != 0 && balance > 0`
   - path: `FORCE_KICK_SWEEP_AND_SETTLE`
   - execute:
     1. `forceKick(token)`
     2. `sweep(token)`
     3. transfer swept balance to `receiver`
     4. `settle(token)`

4. `!active && kicked != 0 && balance == 0`
   - path: `NOOP`
   - do not block future kicks
   - do not attempt reset

5. `!active && kicked == 0 && balance > 0`
   - path: `SWEEP_ONLY`

6. `!active && kicked == 0 && balance == 0`
   - path: `NOOP`

### Why This Is Better

- removes the fragile `disable -> enable` dependency
- uses `forceKick`, which is purpose-built for stale kicked lots with inventory
- leaves stale kicked empty lots alone, since they are non-blocking and do not need cleanup
- makes `resolveAuction()` simpler, not more complex

### Contract Changes

- add `FORCE_KICK_SELECTOR` to `AuctionKicker.sol`
- add `forceKick(address)` to `IAuction.sol`
- replace `PATH_RESET_ONLY`
- replace `PATH_SWEEP_AND_RESET`
- delete `_executeDisableEnable(...)`
- delete `_executeSweepTransferDisableEnable(...)`
- add `_executeForceKickSweepTransferSettle(...)`
- update `previewResolveAuction(...)` path mapping and path reasons
- keep `forceLive` semantics unchanged for live funded lots only

## Planner And Scanner Fix

The planner should stop treating `inactive kicked empty` as a blocking state.

That state should become:

- visible in preview for observability
- non-actionable by default
- non-blocking for future kicks

The scanner and `kick run` should only block on:

- live funded lots
- inactive kicked lots with balance
- inactive clean lots with balance

They should not block on empty stale kicked lots.

## CLI / Operator UX Fix

When a kick is blocked by a stale lot, the operator needs an immediate next step, not just a generic skip.

### Required Output Improvements

For `tidal kick run` and `tidal kick inspect`, when the auction is dirty:

- include the stuck token symbol and address
- include the stuck-state reason
- include the exact settle command to run

Example:

```text
Auction requires settlement before kick
  Attempted Pair: WFRAX -> crvUSD
  Blocked By:     CJPY (0x1cfa...8372)
  Reason:         inactive kicked lot with stranded inventory
  Next Step:      tidal auction settle 0xA00E6b35C23442fa9D5149Cba5dd94623fFE6693 --token 0x1cfa5641c01406aB8AC350dEd7d735ec41298372
```

If multiple stale lots exist:

- show the first blocking token in the panel
- add a short note that `tidal auction settle AUCTION` will prepare all actionable stale lots

### Optional Workflow Improvement

Add an explicit operator workflow flag, not implicit automation:

- `tidal kick run --settle-first`

Behavior:

1. inspect the auction
2. if stale actionable lots exist, prepare and submit `settle` txs first
3. wait for confirmation
4. re-inspect
5. prepare the kick with fresh pricing

This should remain opt-in. Default `kick run` should still fail closed and explain the exact next step.

## Tests

Add or update Solidity tests for:

- inactive funded kicked lot resolves via `forceKick -> sweep -> transfer -> settle`
- inactive kicked empty lot previews as `NOOP`
- live funded lot still requires `forceLive`
- no resolver path uses `disable()` anymore

Add or update Python tests for:

- `kick run` skip panels include blocked token and suggested settle command
- `kick inspect` reports stale funded kicked lots as `Resolve First`
- empty stale kicked lots do not block a future kick
- `tidal auction settle AUCTION` prepares the correct token when only one stale blocker exists

## Rollout Order

1. update `AuctionKicker.sol`
2. update `IAuction.sol`
3. update path reasons and API payloads
4. update planner blocking rules
5. update kick CLI skip rendering
6. add tests
7. deploy the new kicker
8. add it as a mech on `TradeHandler`
9. point server config at the new kicker

## Expected Outcome

After this change:

- stale funded kicked lots are actually resolvable on-chain
- empty stale kicked lots stop causing pointless cleanup work
- `kick run` gives the operator a precise next step
- the contract gets simpler by deleting the reset codepath instead of adding another fallback tree
