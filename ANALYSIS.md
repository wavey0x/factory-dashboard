# Auction Minimum Price And Settlement Analysis

This note analyzes how Tidal currently computes and uses auction `minimumPrice`, and whether that matches the verified `Auction` contract semantics.

Date of analysis: March 29, 2026

## Scope

This analysis covers:

- how the CLI and transaction service compute `startingPrice` and `minimumPrice` for kicks
- how the CLI decides whether `auction settle` should prepare `settle` or `sweep-and-settle`
- whether those behaviors match the contract at `0xeb3746f59befef1f5834239fb65a2a4d88fdb251`

## Primary Sources

- Verified contract source on Etherscan:
  - `https://etherscan.io/address/0xeb3746f59befef1f5834239fb65a2a4d88fdb251#code`
- Etherscan V2 source API:
  - `https://api.etherscan.io/v2/api?chainid=1&module=contract&action=getsourcecode&address=0xeb3746f59befef1f5834239fb65a2a4d88fdb251`
- Etherscan V2 ABI API:
  - `https://api.etherscan.io/v2/api?chainid=1&module=contract&action=getabi&address=0xeb3746f59befef1f5834239fb65a2a4d88fdb251`
- Local code:
  - [`tidal/transaction_service/kicker.py`](/Users/wavey/yearn/tidal/tidal/transaction_service/kicker.py)
  - [`tidal/auction_settlement.py`](/Users/wavey/yearn/tidal/tidal/auction_settlement.py)
  - [`contracts/src/AuctionKicker.sol`](/Users/wavey/yearn/tidal/contracts/src/AuctionKicker.sol)

## Contract Semantics

The verified auction contract uses two different concepts:

- `startingPrice`
  - This is a lot-level value in whole want-token units.
  - It is not stored as raw ERC20 units.
  - The contract uses it to derive an initial per-token price by dividing by the kicked sell amount.

- `minimumPrice`
  - This is not a lot-level quote.
  - This is a per-sell-token floor price in a fixed 1e18-scaled internal unit.
  - The contract compares the current internal price directly against `minimumPrice`.

The relevant contract behavior is:

- `price(_from)` returns the current auction price after dividing the internal price by the want-token scaler.
- `isActive(_from)` is `price(_from) > 0`.
- Internal `_price(...)` returns `0` once the current internal price drops below `minimumPrice`.
- `settle(_from)` requires:
  - the auction is still active
  - the auction balance for `_from` is already zero
- `sweepAndSettle(auction, sellToken)` in [`AuctionKicker.sol`](/Users/wavey/yearn/tidal/contracts/src/AuctionKicker.sol) does:
  - `sweep(sellToken)`
  - transfer swept tokens back to the receiver
  - `settle(sellToken)`

That means `sweep-and-settle` only works while the auction is still active.

## What Tidal Currently Computes

Current kick preparation in [`kicker.py`](/Users/wavey/yearn/tidal/tidal/transaction_service/kicker.py#L846) does:

- `amount_out_normalized = quote_amount_raw / 10^want_decimals`
- `starting_price_raw = ceil(amount_out_normalized * start_buffer)`
- `minimum_price_raw = floor(amount_out_normalized * min_buffer)`

Those values are then passed directly to the kicker contract:

- [`kicker.py`](/Users/wavey/yearn/tidal/tidal/transaction_service/kicker.py#L1203)
- [`AuctionKicker.sol`](/Users/wavey/yearn/tidal/contracts/src/AuctionKicker.sol#L123)

## Finding 1: `startingPrice` Is Structurally Correct

The current `startingPrice` computation is aligned with contract intent.

Why:

- The contract expects `startingPrice` as a whole-token lot quote.
- Tidal computes `startingPrice` from the full-lot quote output amount.
- Passing `427` means "start this lot at 427 want tokens", not "427 wei".

This matches how the contract derives its initial per-token price.

Caveat:

- The variable name `starting_price_raw` is misleading.
- It is not raw ERC20 units.
- It is an unscaled lot-size value.

## Finding 2: `minimumPrice` Is Not Computed In The Contract’s Intended Unit

The current `minimumPrice` computation is not aligned with contract intent.

Today, Tidal computes `minimumPrice` as a buffered full-lot quote amount:

- `minimum_price_raw = floor(full_lot_quote_in_want_tokens * buffer)`

But the contract expects:

- `minimumPrice = floor(want_per_sell_token * buffer * 1e18)`

In other words:

- current Tidal value: lot-level want amount
- contract expected value: per-token floor price in 1e18 internal units

These are different quantities.

## Example

For a quote like:

- sell amount: `1,886.56 CRV`
- quote out: `387.80 reusdscrv`
- min display: `368 reusdscrv`

Tidal currently stores:

- `minimumPrice = 368`

But the contract-intended floor is:

- `368 / 1886.56 = 0.195064... want per CRV`
- scaled for the contract: `195064031888728691`

Those differ by many orders of magnitude.

This is the core bug.

## On-Chain Example: Why `auction settle` Returned `noop`

For auction `0xeb3746f59befef1f5834239fb65a2a4d88fdb251`, direct chain reads on March 29, 2026 showed:

- active token: `CRV`
- want token: `msUSDFRAX3CRV-f`
- want decimals: `18`
- `startingPrice = 411`
- `minimumPrice = 354`
- `price(CRV) = 16273640284037959`
- `available(CRV) = 984634876557164`
- `isActive(CRV) = true`

Because the want token has 18 decimals, the public `price(CRV)` and stored `minimumPrice` are in directly comparable domains for this specific auction.

So the current CLI result:

- `live price > minimumPrice`
- `auction still active above minimumPrice`

is correct for this specific on-chain state.

The important point is that this does not validate the kick-time `minimumPrice` computation. It only shows that the settlement CLI is faithfully reading the small on-chain value that was already stored.

## Finding 3: The Current Floor Stored On Chain Is Likely Far Too Low

For the same auction:

- `startingPrice = 411`
- initial available from `auctions(CRV).initialAvailable = 1969.269748529902292214 CRV`

That implies an initial per-token price of about:

- `411 / 1969.269748529902292214 = 0.2087068063 want per CRV`
- scaled for contract comparison: `208706806320880822`

But the stored `minimumPrice` is only:

- `354`

That is effectively near-zero in contract terms.

So this auction remains active far longer than it would if `minimumPrice` had been set using the contract’s intended unit.

## How `auction settle` Currently Works

Settlement inspection in [`auction_settlement.py`](/Users/wavey/yearn/tidal/tidal/auction_settlement.py) does:

1. Check `isAnActiveAuction()`.
2. Load enabled tokens.
3. Find the active token using `isActive(token)`.
4. Read:
   - `available(active_token)`
   - `price(active_token)`
   - `minimumPrice()`

Decision logic is:

- if `available == 0`: prepare `settle`
- else if `price <= minimumPrice`: prepare `sweep_and_settle`
- else: `noop`

## Finding 4: Plain `settle` Logic Is Correct

This part is correct.

Why:

- the auction contract’s `settle(_from)` requires the auction to still be active
- it also requires the auction’s balance to already be zero

So Tidal’s current rule:

- `available == 0` -> `settle`

matches the contract.

## Finding 5: `sweep-and-settle` Logic Is Only Conditionally Correct

For 18-decimal want tokens, the current compare is dimensionally valid:

- public `price(_from)`
- stored `minimumPrice`

can be compared directly.

For non-18-decimal want tokens, the current compare is wrong.

Reason:

- public `price(_from)` is divided by `wantInfo.scaler`
- `minimumPrice` is not

So for a 6-decimal want token:

- `price(_from)` is in 1e6-style public units
- `minimumPrice` remains in 1e18 internal units

Comparing them directly is not valid.

That means this line is only safe for 18-decimal want tokens:

- [`auction_settlement.py`](/Users/wavey/yearn/tidal/tidal/auction_settlement.py#L214)

## Finding 6: The `sweep-and-settle` Window Is Narrow By Contract Design

Even with a correct comparison, `sweep-and-settle` only works while the auction is still active.

That creates a narrow operational window:

- when current price is still active
- but low enough to justify sweeping instead of waiting for fills

Once the contract’s internal price drops below floor:

- `price(_from)` becomes `0`
- `isActive(_from)` becomes `false`
- `isAnActiveAuction()` becomes `false`
- `settle(_from)` will revert with `!active`
- `sweepAndSettle(...)` will also fail because it ends with `settle(_from)`

So the CLI can only prepare `sweep-and-settle` before the auction actually becomes inactive.

## Finding 7: Current Auto Settlement Has A Recovery Gap

If an auction falls below floor between scans:

- the contract no longer considers it active
- Tidal’s `auction settle` auto mode returns `noop` with "auction has no active lot"

This is not necessarily a local bug. It is a consequence of the contract design plus the current CLI command set.

But it is an operational gap:

- leftover tokens can remain in the auction contract
- `auction settle` cannot recover them
- a governance-only direct `sweep(token)` path would be needed for manual cleanup

## Correctness Summary

### Kick-time pricing

- `startingPrice`
  - semantically correct
  - poorly named in code
- `minimumPrice`
  - semantically incorrect
  - currently computed as a full-lot quote amount
  - should be computed as a per-token floor price scaled to 1e18

### Settlement-time logic

- `settle` trigger
  - correct
- `sweep-and-settle` trigger
  - correct only for 18-decimal want tokens
  - incorrect for non-18-decimal want tokens because units differ
- post-floor inactive recovery
  - currently unsupported by `auction settle`

## Recommended Changes

1. Fix kick-time `minimumPrice` computation.

Use:

- `sell_amount_normalized = sell_amount_raw / 10^sell_decimals`
- `quote_amount_normalized = quote_amount_raw / 10^want_decimals`
- `quoted_price_per_sell = quote_amount_normalized / sell_amount_normalized`
- `minimum_price = floor(quoted_price_per_sell * min_buffer * 1e18)`

2. Keep `startingPrice` as a full-lot unscaled want amount.

That matches the contract.

3. Rename internal fields for clarity.

Examples:

- `starting_price_raw` -> `starting_price_unscaled`
- `minimum_price_raw` -> `minimum_price_scaled_1e18`

4. Fix settlement comparison for non-18-decimal want tokens.

The local inspection should compare values in the same domain, for example:

- `public_floor_price = minimumPrice / wantScaler`
- compare `price(_from)` to `public_floor_price`

or fetch enough state to compare in the contract’s internal domain.

5. Improve CLI displays.

Show:

- lot-level start quote
- per-token live price
- per-token floor price

Those are different quantities and should not share the same raw presentation style.

6. Consider adding a governance sweep command.

That would handle the case where the auction is already inactive but unsold inventory remains in the auction contract.

## Bottom Line

The current `auction settle` outcome for `0xeb3746f59befef1f5834239fb65a2a4d88fdb251` is consistent with the on-chain state.

But the broader system has a real pricing bug:

- Tidal currently computes kick `minimumPrice` in the wrong unit domain.

And it has a settlement correctness gap:

- local `price <= minimumPrice` sweep-and-settle detection is only valid as written when the want token has 18 decimals.

## Implementation Plan

This is the recommended implementation sequence to fix the pricing and settlement issues without creating avoidable regressions.

### Phase 1: Make Units Explicit In Code

Goal:

- stop conflating lot-level quote amounts with per-token floor prices

Changes:

- rename ambiguous fields in the prepare path
- add helper functions for unit conversion instead of open-coded math
- document the unit domain in type and field names

Suggested changes:

- in [`tidal/transaction_service/types.py`](/Users/wavey/yearn/tidal/tidal/transaction_service/types.py)
  - rename `starting_price_raw` to something like `starting_price_unscaled`
  - rename `minimum_price_raw` to something like `minimum_price_scaled_1e18`
- in [`tidal/transaction_service/kicker.py`](/Users/wavey/yearn/tidal/tidal/transaction_service/kicker.py)
  - introduce helpers for:
    - normalized sell amount
    - normalized want quote amount
    - quoted price per sell token
    - lot-level starting price
    - 1e18-scaled per-token minimum price
- in [`tidal/api/services/action_prepare.py`](/Users/wavey/yearn/tidal/tidal/api/services/action_prepare.py)
  - mirror the same naming and helper usage where preview payloads are built

Acceptance criteria:

- a reader can tell from names alone which values are:
  - lot-level unscaled want amounts
  - 1e18-scaled per-token prices
  - public display values

### Phase 2: Fix Kick-Time `minimumPrice` Computation

Goal:

- compute the on-chain floor price in the contract’s intended unit

Correct formula:

- `sell_amount_normalized = sell_amount_raw / 10^sell_decimals`
- `quote_amount_normalized = quote_amount_raw / 10^want_decimals`
- `quoted_price_per_sell = quote_amount_normalized / sell_amount_normalized`
- `minimum_price_scaled_1e18 = floor(quoted_price_per_sell * min_buffer * 1e18)`

Keep:

- `startingPrice = ceil(quote_amount_normalized * start_buffer)`

Changes:

- update [`tidal/transaction_service/kicker.py`](/Users/wavey/yearn/tidal/tidal/transaction_service/kicker.py) to compute:
  - `startingPrice` as a lot-level unscaled want amount
  - `minimumPrice` as a 1e18-scaled per-token floor
- keep passing both directly to [`contracts/src/AuctionKicker.sol`](/Users/wavey/yearn/tidal/contracts/src/AuctionKicker.sol)

Acceptance criteria:

- for an 18-decimal want token example:
  - `startingPrice` remains in whole want-token lot units
  - `minimumPrice` matches the contract-intended scaled floor
- for a non-18-decimal want token example:
  - `minimumPrice` still lands in the correct 1e18-scaled internal domain

### Phase 3: Fix Settlement Inspection And Decision Units

Goal:

- make `auction settle` and sweep-and-settle decisions correct for all want decimals

Changes:

- extend [`tidal/auction_settlement.py`](/Users/wavey/yearn/tidal/tidal/auction_settlement.py) inspection to load enough data to compare prices in the same unit domain
- recommended approach:
  - read `want()`
  - read want token `decimals()`
  - derive `want_scaler = 1e18 / 10^want_decimals`
  - compute `minimum_price_public = minimum_price_scaled_1e18 / want_scaler`
  - compare `price(_from)` against `minimum_price_public`

Alternative:

- compare everything in internal units instead of public units
- this is cleaner semantically, but requires reproducing more of the contract’s internal scaling locally

Recommended decision logic after fix:

- if `available == 0`: actionable `settle`
- else if `active_price_public <= minimum_price_public`: actionable `sweep_and_settle`
- else: `noop`

Acceptance criteria:

- settlement decisions match contract behavior for:
  - 18-decimal want tokens
  - 6-decimal want tokens
  - equality boundary at floor

### Phase 4: Make CLI Output Honest About Units

Goal:

- stop presenting different quantities as if they are the same kind of number

Changes:

- in [`tidal/operator_kick_cli.py`](/Users/wavey/yearn/tidal/tidal/operator_kick_cli.py) and [`tidal/cli_renderers.py`](/Users/wavey/yearn/tidal/tidal/cli_renderers.py):
  - keep `Start quote` as lot-level want amount
  - keep `Quote out` as lot-level want amount
  - add explicit per-token rate lines for:
    - quoted rate
    - start rate
    - floor rate
  - avoid implying that on-chain `minimumPrice` is the same thing as the lot-level `Min quote`
- in `auction settle` noop output:
  - keep showing raw contract values for debugging
  - also show a human-readable public floor price when available

Acceptance criteria:

- an operator can tell at a glance:
  - how many want tokens the lot quotes for
  - what per-token rate the auction currently uses
  - what floor rate the contract is enforcing

### Phase 5: Add Regression Tests That Lock The Semantics Down

Goal:

- prevent future regressions in unit handling

Required tests:

- unit tests for kick preparation:
  - 18-decimal want token
  - 6-decimal want token
  - quote precision / rounding boundaries
- unit tests for settlement decision:
  - sold out -> `settle`
  - active and above floor -> `noop`
  - active and at floor -> `sweep_and_settle`
  - non-18-decimal want token floor compare
- contract-consistency tests:
  - derive expected values from the verified `Auction` pricing formula
  - assert local math agrees

Files likely touched:

- [`tests/unit/test_txn_kicker.py`](/Users/wavey/yearn/tidal/tests/unit/test_txn_kicker.py)
- [`tests/unit/test_auction_settlement.py`](/Users/wavey/yearn/tidal/tests/unit/test_auction_settlement.py)
- [`tests/unit/test_operator_auction_cli.py`](/Users/wavey/yearn/tidal/tests/unit/test_operator_auction_cli.py)
- possibly contract tests in [`contracts/test/AuctionKicker.t.sol`](/Users/wavey/yearn/tidal/contracts/test/AuctionKicker.t.sol)

Acceptance criteria:

- tests prove correctness for both 18-decimal and non-18-decimal want tokens

### Phase 6: Audit Existing Live Auctions

Goal:

- identify auctions already kicked with an under-scaled `minimumPrice`

Changes:

- add a one-off audit script or operator command that:
  - reads active auctions
  - reconstructs expected floor price from stored sell amount and current preview logic when possible
  - flags auctions where on-chain `minimumPrice` is obviously too small

This does not need to block the code fix, but it is operationally important.

Acceptance criteria:

- operators can identify auctions whose floors were set incorrectly before the fix

### Phase 7: Decide How To Handle Inactive Residual Auctions

Goal:

- address the current operational gap after an auction falls below floor and becomes inactive

Options:

- leave as-is and require governance to recover manually
- add a dedicated governance-only sweep command in the operator surface
- add a diagnostics-only command that explicitly reports:
  - inactive residual inventory
  - why `settle` is unavailable
  - what governance action is needed

This is adjacent to the pricing fix, not the core bug itself.

## Recommended Delivery Order

1. Phase 1: explicit units and helper functions
2. Phase 2: fix kick-time `minimumPrice`
3. Phase 5: add or update core tests immediately around that change
4. Phase 3: fix settlement comparison units
5. Phase 4: improve CLI displays
6. Phase 6: audit existing live auctions
7. Phase 7: decide on inactive residual handling

## Minimum Safe Ship Scope

If this needs to be broken into a first safe patch and later improvements, the minimum safe ship is:

1. fix kick-time `minimumPrice` computation
2. fix settlement comparison for non-18-decimal want tokens
3. add regression tests for both

That addresses the actual correctness bugs. The CLI presentation and audit tooling can follow immediately after.
