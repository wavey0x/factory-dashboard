# AuctionKicker Update Plan

## Goal

Update `contracts/src/AuctionKicker.sol` for the modern auction interface so each kick sets both `startingPrice` and `minimumPrice`, then refresh the relevant tests and ABI call sites.

## Verified Auction Surface

Verified on March 16, 2026 using the example auction at `0x1721A935063EcFBc1542f15E028e7c2FCe52B169`:

- `setStartingPrice(uint256)` still exists
- `minimumPrice() -> uint256` exists
- `setMinimumPrice(uint256)` exists
- `receiver() -> address` exists
- `kick(address)` still exists

Important: `startingPrice` and `minimumPrice` are not the same unit. `startingPrice` is a lot-style value in want units, while `minimumPrice` is a scaled per-token floor. Both are derived from the quote in the Python caller (see step 5).

## Contract Changes

### 1. Extend `IAuction`

File: `contracts/src/interfaces/IAuction.sol`

Add:

- `function minimumPrice() external view returns (uint256);`
- `function setMinimumPrice(uint256 _minimumPrice) external;`
- `function receiver() external view returns (address);`

### 2. Update `AuctionKicker`

File: `contracts/src/AuctionKicker.sol`

Add:

- `SET_MINIMUM_PRICE_SELECTOR = bytes4(keccak256("setMinimumPrice(uint256)"))`

Change the public entrypoint:

- Replace the current 5-arg `kick(strategy, auction, sellToken, sellAmount, startingPrice)`
- With a 6-arg version that also accepts `minimumPrice`

Do not add an overload. The Python caller uses `contract.functions.kick(...)`, and overloading will make ABI usage and call resolution worse.

Keep:

- `require(startingPrice != 0, "starting price zero");`

Do not require `minimumPrice != 0` unless policy changes. The modern auction allows a zero floor.

Require order (want first, then receiver — preserves existing test behaviour for want-mismatch):

1. `require(IAuction(auction).want() == IStrategy(strategy).want(), "want mismatch");`
2. `require(IAuction(auction).receiver() == strategy, "receiver mismatch");`

Expand the weiroll program from 3 commands / 5 state slots to 4 commands / 6 state slots:

State layout:

| Index | Value          | Used by              |
|-------|----------------|----------------------|
| 0     | strategy       | transferFrom (from)  |
| 1     | auction        | transferFrom (to)    |
| 2     | sellAmount     | transferFrom (amount)|
| 3     | startingPrice  | setStartingPrice     |
| 4     | minimumPrice   | setMinimumPrice      |
| 5     | sellToken      | kick (shifted from 4)|

Commands:

1. `cmdCall(TRANSFER_FROM_SELECTOR, 0, 1, 2, sellToken)`
2. `cmdCall(SET_STARTING_PRICE_SELECTOR, 3, UNUSED, UNUSED, auction)`
3. `cmdCall(SET_MINIMUM_PRICE_SELECTOR, 4, UNUSED, UNUSED, auction)`
4. `cmdCall(KICK_SELECTOR, 5, UNUSED, UNUSED, auction)`

Extend the `Kicked` event to emit `minimumPrice`:

- Update event declaration in `AuctionKicker.sol` (line 18)
- Update `emit Kicked(...)` call (line 74)

## Test Changes

### 3. Refresh the fork fixtures

File: `contracts/test/AuctionKicker.t.sol`

The current `AUCTION = 0x9D252f3da6E1c59EF1804657b59fC4129f70eD04` fixture is an older auction variant and does not expose `setMinimumPrice`.

Use the migrated `1.0.4` auction for the existing strategy:

- strategy: `0x9AD3047D578e79187f0FaEEf26729097a4973325`
- new auction: `0x785cf728913e92dc5b24162dcbee7a41e7de5747`

This mapping is already present in `.cache/auction_migration_plan.json`.

Replace `ALT_AUCTION` (`0x2232Fd50CBF9d500B4b624Bfe126F09caf3d24B8`) with:

- `0x1721A935063EcFBc1542f15E028e7c2FCe52B169` — a verified 1.0.4 auction with a different `want` (`0xee35...` vs strategy's `0x7f86...`)

Fixture properties from cache:

| Fixture       | want matches strategy? | receiver matches strategy? |
|---------------|------------------------|---------------------------|
| new AUCTION   | yes                    | yes (`receiver == strategy`) |
| new ALT_AUCTION | no (`0xee35...`)     | no (`0x0d72...`)          |

Because want is checked before receiver, `ALT_AUCTION` will revert with "want mismatch" naturally. For `test_revert_receiverMismatch`, use `vm.mockCall` to stub `want()` on `ALT_AUCTION` to return the strategy's want, so it passes the want check and hits the receiver guard.

### 4. Update test cases

Update the `Kicked` event re-declaration in the test contract (line 24) to include `minimumPrice`.

Update all calls to `kicker.kick(...)` to pass `minimumPrice` (6 args).

Adjust the happy path to:

- pass both `startingPrice` and `minimumPrice`
- assert token transfer still occurs
- assert `IAuction(AUCTION).startingPrice() == startingPrice`
- assert `IAuction(AUCTION).minimumPrice() == minimumPrice`
- assert the extended `Kicked` event

Keep and update existing revert tests:

- unauthorized caller — add 6th arg
- zero starting price — add 6th arg
- want mismatch — update to use new `ALT_AUCTION`

Additional tests:

- `test_revert_receiverMismatch` — use `vm.mockCall` to stub `ALT_AUCTION.want()` so it passes the want check, then assert "receiver mismatch"
- `test_minimumPrice_zeroAllowed` — pass `minimumPrice = 0` and confirm no revert

## ABI / Caller Changes

### 5. Update off-chain ABI and transaction builder

Files:

- `factory_dashboard/chain/contracts/abis.py`
- `factory_dashboard/transaction_service/kicker.py`
- `factory_dashboard/transaction_service/types.py`

#### ABI

Update `AUCTION_KICKER_ABI` to the new 6-arg `kick(...)` — add `minimumPrice` as the 6th `uint256` input.

#### minimumPrice derivation

Both prices are derived from the same quote in `kicker.py`:

- `startingPrice = ceil(quote * (1 + start_price_buffer_bps / 10000))` — quote + buffer (high side, existing logic)
- `minimumPrice = floor(quote * (1 - min_price_buffer_bps / 10000))` — quote - buffer (low side, new)

Add `min_price_buffer_bps` (default `500` = 5%) to:

- `AuctionKicker.__init__` parameter list in `kicker.py`
- Already added to `config.yaml` (`txn_min_price_buffer_bps: 500`) and `config.py` (`Settings.txn_min_price_buffer_bps`)
- Wire through `runtime.py` (line 189, same pattern as `start_price_buffer_bps`)

Compute `minimum_price_raw` immediately after `starting_price_raw` in `kicker.py` (around line 186), using `ROUND_FLOOR` instead of `ROUND_CEILING`. Clamp to 0 if the result goes negative (can happen with very small quotes).

#### Transaction builder

Update `kick_fn` call (line 233-239) to pass `minimum_price_raw` as the 6th argument.

#### Types and persistence

- Add `minimum_price: str | None = None` to `KickResult` in `types.py`
- Add `minimum_price` to `_insert_kick_tx` row dict and `_fail` helper
- Include `minimum_price` in the confirmation summary dict (line 286-307)
- Include `minimum_price` in log context (`log_ctx`, line 202)

### 6. Update Python unit tests

File: `tests/unit/test_txn_kicker.py`

All tests that mock `contract.functions.kick(...)` pass 5 args — update to 6. Affected tests:

- `test_kick_estimate_failed`
- `test_kick_gas_estimate_over_cap`
- `test_kick_confirmed`
- `test_kick_reverted`
- `test_kick_receipt_timeout_stays_submitted`
- `test_kick_confirm_fn_declined` / `_accepted` / `_no_confirm_fn`
- All priority fee tests
- All starting price tests

Add `min_price_buffer_bps=500` to `_make_kicker` defaults.

Add test:

- `test_minimum_price_derived_from_quote` — verify `minimum_price_raw = floor(quote * 0.95)` and that it appears in `KickResult` and the persisted row.

## Docs

### 7. Update contract docs

File: `contracts/README.md`

Change the mech description from a fixed 3-step program to a fixed 4-step program:

1. transfer reward token from strategy to auction
2. set auction starting price
3. set auction minimum price
4. kick auction

## Verification

Run:

```bash
cd contracts
forge test --match-contract AuctionKickerTest
```

Python tests:

```bash
pytest tests/unit/test_txn_kicker.py
```

## Sources

- Example modern auction verified source and ABI:
  `https://etherscan.io/address/0x1721A935063EcFBc1542f15E028e7c2FCe52B169#code`
- Local migrated fixture mapping:
  `.cache/auction_migration_plan.json`
