# Roles Plan

## Goal

Let the same operator account that is an `AuctionKicker` keeper also run `enable-tokens` on auctions, without requiring that account to be a direct mech on the `TradeHandler`.

## Current split

Today there are two different permission models:

- `kick` / `kickExtended` / `sweepAndSettle`
  - signer only needs to be `owner` or `keeper` on `AuctionKicker`
  - `AuctionKicker` itself is the mech that calls `TradeHandler.execute(...)`

- `enable-tokens`
  - signer must be a direct mech on the auction governance / `TradeHandler`
  - both `tidal-server auction enable-tokens` and API prepare currently target `TradeHandler.execute(...)` directly

This is why one account can kick but cannot enable tokens.

## Recommendation

Add a dedicated `enableTokens` function to `AuctionKicker`, and route `enable-tokens` through that helper when the auction governance matches the standard `TradeHandler`.

Do **not** add a generic arbitrary `execute(bytes32[],bytes[])` passthrough to `AuctionKicker`.

That would be too broad. The missing capability is narrow and should stay narrow.

## Why this is the right shape

- reuses the existing keeper role instead of introducing another privileged signer requirement
- keeps the user-facing role model simpler: keeper account can manage kick lifecycle tasks
- is safer than giving keepers a general-purpose `TradeHandler.execute(...)` passthrough
- reuses the same on-chain trust boundary already used for kicking

## Contract plan

### 1. Add a dedicated function on `AuctionKicker`

Add:

```solidity
function enableTokens(address auction, address[] calldata sellTokens) external onlyKeeperOrOwner
```

Behavior:

- require `sellTokens.length > 0`
- require `IAuction(auction).governance() == tradeHandler`
- build wei-roll commands that call `enable(address)` on the auction for each token
- call `ITradeHandler(tradeHandler).execute(commands, state)`

No new storage.
No generic passthrough.

### 2. Keep validation narrow

Do **not** add on-chain discovery heuristics or token probing logic.

The contract should not try to decide whether a token *should* be enabled.
It should only execute the explicit token list prepared off-chain.

### 3. Optional event

Optional:

```solidity
event TokensEnabled(address indexed auction, uint256 tokenCount);
```

This is nice to have, not required for v1.

I would not block the feature on adding a new event.

## Python / API plan

### 4. Extend the ABI surface

Update `tidal/chain/contracts/abis.py` to include the new `AuctionKicker.enableTokens(...)` ABI entry.

### 5. Introduce a small execution-mode split for enable-tokens

Centralize enable execution planning in `tidal/ops/auction_enable.py`.

Add a small internal execution mode:

- `auction_kicker`
- `trade_handler`

Recommended rule:

- if `inspection.governance == YEARN_AUCTION_REQUIRED_GOVERNANCE_ADDRESS`
- and `settings.auction_kicker_address` is configured
- then prefer `auction_kicker`
- otherwise fall back to the current direct `trade_handler` mode

This keeps the standard Yearn path clean while preserving the existing fallback for non-standard governance.

### 6. Refactor `AuctionTokenEnabler` around a shared execution plan

Add a small dataclass, e.g. `EnableExecutionPlan`, containing:

- `mode`
- `to_address`
- `data`
- `gas_estimate`
- `call_succeeded`
- `error_message`
- `authorization_target`
- `sender_authorized`

Use this from both:

- direct server CLI path
- API prepare path

This avoids duplicating the routing / authorization logic in two places.

### 7. Kicker-mode preview and authorization

For `auction_kicker` mode:

- preview by `eth_call` / gas estimate against `AuctionKicker.enableTokens(...)`
- authorization check becomes:
  - `AuctionKicker.owner() == sender`
  - or `AuctionKicker.keeper(sender) == true`

For `trade_handler` fallback mode:

- keep current preview against `TradeHandler.execute(...)`
- keep current mech authorization check

### 8. API prepare change

Update `prepare_enable_tokens_action` in `tidal/api/services/action_prepare.py`:

- build the token selection exactly as today
- choose execution mode
- encode either:
  - `AuctionKicker.enableTokens(auction, tokens)`
  - or legacy `TradeHandler.execute(commands, state)`
- return the chosen target and preview metadata in the prepared action

## CLI plan

### 9. `tidal-server auction enable-tokens`

Update direct server execution to use the shared execution-plan path.

The command behavior stays the same, but the broadcast target changes:

- standard Yearn auction: signer sends tx to `AuctionKicker`
- fallback auction: signer sends tx to `TradeHandler`

### 10. `tidal auction enable-tokens`

Update the API-backed CLI to display the same plan cleanly.

The command UX should stay unchanged.

### 11. Improve wording in preview output

Current wording is mech-specific.

Change it to something generic like:

- `Execution authorization: yes/no`
- `Authorization target: AuctionKicker 0x...`

or:

- `Authorization mode: kicker keeper`
- `Authorization mode: trade handler mech`

The important part is that the preview clearly tells the operator which role is being checked.

## Scope boundary

### 12. Do not turn `AuctionKicker` into a generic governance router

Avoid:

- arbitrary `execute(...)` passthrough
- arbitrary auction function dispatch
- arbitrary target contracts

That would expand keeper power much more than needed.

The right v1 is a single dedicated helper for token enablement.

## Tests

### 13. Contract tests

Extend `contracts/test/AuctionKicker.t.sol` to cover:

- keeper can call `enableTokens`
- non-keeper cannot
- tokens are enabled through `TradeHandler.execute(...)`
- governance mismatch reverts

### 14. Python unit tests

Add / update tests for:

- shared execution-plan selection in `tests/unit/test_auction_enable.py`
- API prepare using `AuctionKicker` mode in `tests/unit/test_action_prepare.py`
- direct CLI happy path in `tests/unit/test_operator_auction_cli.py`
- fallback legacy `trade_handler` mode still working for non-standard governance

### 15. Integration tests

Update `tests/integration/test_api_control_plane.py` to assert the prepared transaction target for `enable-tokens` is:

- `settings.auction_kicker_address` for standard governance
- `inspection.governance` for fallback mode

## Deployment plan

### 16. On-chain rollout

1. deploy the updated `AuctionKicker`
2. add the new `AuctionKicker` as a mech on `TradeHandler`
3. grant keeper access to the intended operator account(s)
4. update `auction_kicker_address` in server config

### 17. App rollout

1. deploy updated Tidal API/server
2. upgrade CLI installs as needed
3. verify `enable-tokens` with:
   - keeper-only account
   - direct mech account
   - standard governance auction
   - fallback non-standard governance auction

## Downstream note

Checked the read-only `wavey-api` repo for a Tidal proxy/service layer tied to this payload shape and did not find an active `services/tidal.py` or route integration that would need changes for this feature.

So this plan is contained to:

- Solidity contract
- Tidal API prepare path
- Tidal CLIs
- tests/docs
