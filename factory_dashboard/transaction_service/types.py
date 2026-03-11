"""Types for the transaction service."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class KickCandidate:
    """Row from the shortlist query — a (strategy, token) pair above threshold."""

    strategy_address: str
    token_address: str
    auction_address: str
    normalized_balance: str
    price_usd: str
    want_address: str
    usd_value: float
    decimals: int


@dataclass(slots=True)
class KickDecision:
    """Evaluator output — whether to kick and why."""

    candidate: KickCandidate
    action: str  # "KICK" or "SKIP"
    skip_reason: str | None = None  # "COOLDOWN", "CIRCUIT_BREAKER"


@dataclass(slots=True)
class KickResult:
    """Kicker output — what happened when we tried to kick."""

    kick_tx_id: int
    status: str  # CONFIRMED, REVERTED, SUBMITTED, ESTIMATE_FAILED, ERROR, DRY_RUN, USER_SKIPPED
    tx_hash: str | None = None
    gas_used: int | None = None
    gas_price_gwei: str | None = None
    block_number: int | None = None
    error_message: str | None = None
    sell_amount: str | None = None
    starting_price: str | None = None
    live_balance_raw: int | None = None
    usd_value: str | None = None


@dataclass(slots=True)
class TxnRunResult:
    """Summary of a single evaluation cycle."""

    run_id: str
    status: str
    candidates_found: int
    kicks_attempted: int
    kicks_succeeded: int
    kicks_failed: int
