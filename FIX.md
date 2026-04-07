# Stale Lot Sweep Fix

## Goal

Handle the narrow edge case where:

- a lot is stale and funded
- `resolveAuction()` fails because the reset step hits a token-specific approval incompatibility
- a plain `sweep()` would still succeed

Live example:

- auction: `0xA00E6b35C23442fa9D5149Cba5dd94623fFE6693`
- token: `CJPY` (`0x1cfa5641c01406aB8AC350dEd7d735ec41298372`)
- `sweep(token)` works
- `disable(token)` reverts with `Amount is zero.`

## Decision

Do not redesign the resolver around this edge case.

Instead:

1. keep `resolveAuction()` as the normal cleanup path
2. add a dedicated manual sweep primitive to `AuctionKicker`
3. treat `inactive kicked empty` as non-blocking after a sweep
4. improve CLI output so the operator knows exactly what token is stuck and what command to run next

## Contract Changes

Add a keeper-only helper to [AuctionKicker.sol](/Users/wavey/yearn/tidal/contracts/src/AuctionKicker.sol):

- `sweepAuction(address auction, address sellToken)`

Behavior:

1. validate:
   - `IAuction(auction).governance() == tradeHandler`
   - `sellToken != address(0)`
   - `sellToken != IAuction(auction).want()`
2. read:
   - `receiver = IAuction(auction).receiver()`
   - `balance = IERC20(sellToken).balanceOf(auction)`
3. execute through `TradeHandler`:
   - `auction.sweep(sellToken)`
   - `IERC20(sellToken).transfer(receiver, balance)`
4. emit a dedicated event, for example:
   - `AuctionSwept(address indexed auction, address indexed sellToken, address receiver, uint256 recoveredBalance)`

Notes:

- this is intentionally manual and bespoke
- it is not a replacement for `resolveAuction()`
- it exists to clear rare tokens that cannot go through the reset path cleanly

## Planner And Classifier Changes

After a manual sweep, the lot becomes:

- `!active`
- `kicked != 0`
- `balance == 0`

That state should not block future kicks.

Update the planner and settlement classifier so:

- `inactive kicked empty` is visible for observability
- `inactive kicked empty` is not actionable by default
- `inactive kicked empty` does not block `kick run`

No other resolver-state policy needs to change for this fix.

## CLI Changes

Add a manual operator command:

- `tidal auction sweep AUCTION --token TOKEN`

This should prepare and send `AuctionKicker.sweepAuction(...)`.

When `kick run` or `kick inspect` encounters a blocking stale lot, include:

- blocked token symbol
- blocked token address
- blocker reason
- exact next-step command

Example:

```text
Auction requires settlement before kick
  Attempted Pair: WFRAX -> crvUSD
  Blocked By:     CJPY (0x1cfa...8372)
  Reason:         inactive kicked lot with stranded inventory
  Next Step:      tidal auction settle 0xA00E6b35C23442fa9D5149Cba5dd94623fFE6693 --token 0x1cfa5641c01406aB8AC350dEd7d735ec41298372
```

If gas estimation for `resolveAuction()` fails on that blocker, upgrade the hint:

```text
Resolve failed for CJPY. This token may require a manual sweep.
Next Step: tidal auction sweep 0xA00E6b35C23442fa9D5149Cba5dd94623fFE6693 --token 0x1cfa5641c01406aB8AC350dEd7d735ec41298372
```

This keeps the normal path simple while giving the operator a precise escape hatch.

## Tests

Add Solidity tests for:

- `sweepAuction()` sweeps the auction balance and forwards it to `receiver`
- `sweepAuction()` rejects `want` and governance-mismatched auctions

Add Python tests for:

- `inactive kicked empty` no longer blocks `kick run`
- `kick run` skip output includes blocked token and suggested command
- failed `resolveAuction()` estimates produce the manual sweep hint
- `tidal auction sweep` prepares the correct tx

## Rollout

1. add `sweepAuction()` and event to the contract
2. expose it in ABI, API prepare flow, and CLI
3. update planner blocking rules for `inactive kicked empty`
4. improve kick-side hinting
5. add tests
6. deploy the new kicker and add it as a mech

## Outcome

After this change:

- normal stale lots still use `resolveAuction()`
- rare incompatible tokens can be cleared with a simple manual sweep
- a successful sweep leaves the lot non-blocking for future kicks
- the operator gets a concrete next-step command instead of a generic skip
