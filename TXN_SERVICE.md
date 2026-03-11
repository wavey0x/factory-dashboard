# Transaction Service

Sidecar process that kicks Yearn auctions when a strategy's reward token balance exceeds a USD threshold. Reads the scanner's SQLite cache to shortlist candidates, re-reads live on-chain balance before sending. Dry-run by default; `--live` flag to send.

Runs alongside the scanner as a separate process (`factory-dashboard txn once` / `txn daemon`). The scanner never needs signing keys. Live mode acquires an `fcntl.flock()` lock (auto-releases on crash) to prevent duplicate sends.

## Target Contract

**AuctionKicker** `0x2a76c6aD151Af2edBe16755fC3BFF67176f01071`

```solidity
function kick(address strategy, address auction, address sellToken, uint256 sellAmount, uint256 startingPrice) external;  // onlyKeeperOrOwner
function owner() public view returns (address);
function keeper(address) public view returns (bool);
function tradeHandler() public view returns (address);  // 0xb634316E...
```

**Must resolve via fork test before implementation (rewrite this section with exact answers after Step 0):**
- Exact units for `sellAmount` and `startingPrice`. Document rounding rules.
- Whether AuctionKicker handles token approvals or strategy must pre-approve.
- Whether `estimateGas` reliably reverts on bad inputs (no `kickable()` view exists).
- Keeper auth: confirm signer is registered or determine `setKeeper` flow.

---

## Configuration

Added to existing `Settings` in `config.py`:

```bash
TXN_USD_THRESHOLD=100                # Min USD value to kick
TXN_MAX_GAS_PRICE_GWEI=50            # Hard ceiling — skip if exceeded
TXN_MAX_PRIORITY_FEE_GWEI=2          # Max tip
TXN_MAX_GAS_LIMIT=500000             # Cap on estimatedGas * 1.2
TXN_START_PRICE_BUFFER_BPS=1000      # +10% above reference price
TXN_MAX_DATA_AGE_SECONDS=600         # Reject stale scanned_at / price_fetched_at
TXN_KEYSTORE_PATH=                   # UTC/JSON keystore file
TXN_KEYSTORE_PASSPHRASE=             # From .env, never committed
TXN_COOLDOWN_SECONDS=3600            # Per (strategy, token) pair
```

---

## Schema

Alembic migration adds two tables.

**`txn_runs`** — INSERT at start with status=RUNNING, UPDATE at end with final counts:

| Column | Type |
|--------|------|
| `run_id` | TEXT PK |
| `started_at` | TEXT |
| `finished_at` | TEXT nullable |
| `status` | TEXT — RUNNING / SUCCESS / PARTIAL_SUCCESS / FAILED / DRY_RUN |
| `candidates_found` | INTEGER |
| `kicks_attempted` | INTEGER |
| `kicks_succeeded` | INTEGER |
| `kicks_failed` | INTEGER |
| `live` | INTEGER |
| `error_summary` | TEXT nullable |

**`kick_txs`** — written incrementally as each candidate is processed, not batched at end-of-run:

| Column | Type |
|--------|------|
| `id` | INTEGER PK |
| `run_id` | TEXT FK |
| `strategy_address` | TEXT |
| `token_address` | TEXT |
| `auction_address` | TEXT |
| `sell_amount` | TEXT — from live balanceOf, passed to kick() |
| `starting_price` | TEXT — passed to kick() |
| `price_usd` | TEXT |
| `usd_value` | TEXT |
| `status` | TEXT — see below |
| `tx_hash` | TEXT nullable |
| `gas_used` | INTEGER nullable |
| `gas_price_gwei` | TEXT nullable |
| `block_number` | INTEGER nullable |
| `error_message` | TEXT nullable |
| `created_at` | TEXT |

Index: `(strategy_address, token_address, created_at DESC)` for cooldown lookups.

### `kick_txs` statuses

```
DRY_RUN          — evaluated in dry-run mode. Terminal.
ESTIMATE_FAILED  — estimateGas reverted. Terminal.
ERROR            — unexpected failure before broadcast (signing, RPC down). Terminal.
SUBMITTED        — tx broadcast succeeded, receipt pending. Transitions to CONFIRMED or REVERTED.
CONFIRMED        — receipt received, tx succeeded. Terminal.
REVERTED         — receipt received, tx reverted. Terminal.
```

Strategies with no auction, below-threshold balances, and stale data are filtered during shortlisting and logged only — no `kick_txs` row.

---

## Components

```
factory_dashboard/
  transaction_service/
    __init__.py
    evaluator.py
    kicker.py
    service.py
    signer.py
    types.py
```

ABI added to existing `chain/contracts/abis.py`. Wired from `runtime.py`. CLI added to `cli.py`.

### `types.py`

`KickCandidate` (from SQLite shortlist), `KickDecision` (evaluator output), `KickResult` (kicker output).

### `signer.py`

Decrypts keystore with passphrase at startup. Exposes `sign_transaction()`. Key never logged.

### `evaluator.py`

**Shortlist** (DB query): join `strategy_token_balances_latest` + `tokens` + `strategies`. Filter:
- `auction_address IS NOT NULL` (strategies without auctions are skipped here)
- `price_status = 'SUCCESS'` and `price_usd IS NOT NULL`
- `normalized_balance * price_usd >= TXN_USD_THRESHOLD`
- `scanned_at` and `price_fetched_at` within `TXN_MAX_DATA_AGE_SECONDS`

**Pre-send checks** (per candidate):
- Cooldown: query most recent `kick_txs` row for this (strategy, token). CONFIRMED and SUBMITTED within `TXN_COOLDOWN_SECONDS` block. Other statuses do not.
- Cooldown: CONFIRMED and SUBMITTED within `TXN_COOLDOWN_SECONDS` block.

### `kicker.py`

Per candidate:
1. Re-read `balanceOf(strategy)` on-chain → `sellAmount`
2. Recalculate USD value with live balance; reject if below threshold
3. Calculate `startingPrice` from `price_usd * (1 + buffer_bps / 10_000)`
4. Check signer ETH balance >= floor
5. Check gas price <= ceiling
6. `estimateGas` — revert → INSERT ESTIMATE_FAILED row, skip
7. Gas limit = `min(estimate * 1.2, TXN_MAX_GAS_LIMIT)`; reject if estimate exceeds cap
8. Sign + send → INSERT SUBMITTED row with tx_hash
9. Wait for receipt (120s timeout) → UPDATE to CONFIRMED or REVERTED
10. Receipt timeout → row stays SUBMITTED, log warning, continue

Sequential only. One in-flight tx at a time.

### `service.py`

`TxnService.run_once(live: bool)`:
1. If live: acquire `fcntl.flock()`, exit if held
2. INSERT `txn_runs` with status=RUNNING
3. Shortlist candidates (evaluator)
4. For each candidate:
   - Dry-run: INSERT DRY_RUN row, log
   - Live: call kicker (writes incrementally per steps above)
5. UPDATE `txn_runs` with final counts + status
6. Release lock

---

## CLI

```
factory-dashboard txn once              # Dry-run: evaluate + log
factory-dashboard txn once --live       # Evaluate + send
factory-dashboard txn daemon            # Dry-run loop
factory-dashboard txn daemon --live     # Live loop with file lock
```

---

## Safety

1. Dry-run by default. `--live` required to send.
2. `sellAmount` from live `balanceOf`, never cached.
3. Stale data → reject. `price_status` must be SUCCESS.
4. Strategies without `auction_address` filtered at shortlist.
5. Gas price > ceiling → skip.
6. Gas limit = `estimate * 1.2`, capped by `TXN_MAX_GAS_LIMIT`.
7. Cooldown per (strategy, token) — CONFIRMED and SUBMITTED block.
10. `fcntl.flock()`: one live process at a time, auto-releases on crash.
11. `estimateGas` before every send. Revert = skip.
12. SUBMITTED rows survive crashes and block resends until aged out.
13. Key never logged.

---

## Implementation Order

### Step 0: Fork test — resolve contract semantics
- [ ] `tests/fork/test_fork_kick.py` against Anvil
- [ ] Confirm `sellAmount` units, `startingPrice` encoding, rounding rules
- [ ] Confirm approval flow
- [ ] Confirm `estimateGas` reverts on bad inputs
- [ ] Confirm keeper auth
- [ ] Add AuctionKicker ABI to `chain/contracts/abis.py`
- [ ] **Rewrite Target Contract section with exact answers**

### Step 1: Foundation
- [ ] Txn settings in `Settings`, env vars in `.env.example`
- [ ] `transaction_service/` with `types.py`

### Step 2: Signer + kicker
- [ ] `signer.py` + `kicker.py`
- [ ] Extend `Web3Client`: `send_raw_transaction()`, `get_transaction_receipt()`, `get_balance()`
- [ ] Unit tests

### Step 3: Evaluator + service
- [ ] `evaluator.py` + `service.py`
- [ ] Wire from `runtime.py`
- [ ] Unit tests for evaluator

### Step 4: Persistence + CLI
- [ ] Alembic migration
- [ ] Repository classes
- [ ] CLI commands
- [ ] Integration test: seed DB → dry-run → assert rows
- [ ] Integration test: broadcast succeeds, receipt times out, rerun must not resend

### Step 5: Hardening
- [ ] Fork smoke test with real data
- [ ] Verify lock under concurrent launch
- [ ] Verify SUBMITTED blocks resend after simulated crash

## V1 cuts

- Per-token thresholds
- Concurrent sends
- Persisting routine skips
- Telegram alerts
