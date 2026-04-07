"""Shared auction settlement inspection and decision helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

from eth_utils import to_checksum_address

from tidal.chain.contracts.abis import AUCTION_KICKER_ABI
from tidal.chain.contracts.erc20 import ERC20Reader
from tidal.chain.contracts.multicall import MulticallClient
from tidal.normalizers import normalize_address
from tidal.scanner.auction_state import AuctionStateReader
from tidal.transaction_service.types import AuctionInspection

SettlementMethod = Literal["auto", "settle", "sweep_and_settle"]
SettlementDecisionStatus = Literal["actionable", "noop", "error"]
SettlementOperationType = Literal["resolve_auction"]


@dataclass(slots=True)
class AuctionSettlementDecision:
    status: SettlementDecisionStatus
    operation_type: SettlementOperationType | None
    token_address: str | None
    reason: str


@dataclass(slots=True)
class AuctionSettlementCall:
    operation_type: SettlementOperationType
    token_address: str
    target_address: str
    data: str


def normalize_settlement_method(value: str) -> SettlementMethod:
    normalized = value.strip().lower().replace("-", "_")
    if normalized in {"auto", "settle", "sweep_and_settle"}:
        return normalized  # type: ignore[return-value]
    raise ValueError("expected 'auto', 'settle', or 'sweep-and-settle'")


async def inspect_auction_settlement(  # noqa: ANN001
    web3_client,
    settings,
    auction_address: str,
    token_address: str | None = None,
) -> AuctionInspection:
    normalized_auction = normalize_address(auction_address)
    normalized_token = normalize_address(token_address) if token_address else None
    multicall_client = MulticallClient(
        web3_client,
        settings.multicall_address,
        enabled=settings.multicall_enabled,
    )
    reader = AuctionStateReader(
        web3_client=web3_client,
        multicall_client=multicall_client,
        multicall_enabled=settings.multicall_enabled,
        multicall_auction_batch_calls=settings.multicall_auction_batch_calls,
    )
    erc20_reader = ERC20Reader(
        web3_client,
        multicall_client=multicall_client,
        multicall_enabled=settings.multicall_enabled,
        multicall_balance_batch_calls=settings.multicall_balance_batch_calls,
    )

    active_flags = await reader.read_bool_noargs_many([normalized_auction], "isAnActiveAuction")
    is_active_auction = active_flags.get(normalized_auction)

    enabled_tokens_result = await reader.read_address_array_noargs_many([normalized_auction], "getAllEnabledAuctions")
    enabled_tokens: list[str] = enabled_tokens_result.get(normalized_auction) or []

    probe_tokens: set[str] = set(enabled_tokens)
    if normalized_token is not None:
        probe_tokens.add(normalized_token)
    ordered_tokens = tuple(sorted(probe_tokens))
    probe_pairs = [(normalized_auction, token_address) for token_address in ordered_tokens]

    token_active: dict[tuple[str, str], bool | None] = {}
    balance_by_pair: dict[tuple[str, str], int | None] = {}
    kicked_by_pair: dict[tuple[str, str], int | None] = {}

    if probe_pairs:
        token_active = await reader.read_bool_arg_many(probe_pairs, "isActive")
        balance_by_pair, _ = await erc20_reader.read_balances_many(probe_pairs)
        kicked_by_pair = await reader.read_uint_arg_many(probe_pairs, "kicked")

    active_tokens = tuple(
        sorted(
            token
            for token in ordered_tokens
            if token_active.get((normalized_auction, token)) is True
        )
    )
    inactive_tokens_with_balance = tuple(
        sorted(
            token
            for token in ordered_tokens
            if token_active.get((normalized_auction, token)) is not True
            and (balance_by_pair.get((normalized_auction, token)) or 0) > 0
        )
    )
    inactive_tokens_with_kick = tuple(
        sorted(
            token
            for token in ordered_tokens
            if token_active.get((normalized_auction, token)) is not True
            and (kicked_by_pair.get((normalized_auction, token)) or 0) > 0
        )
    )
    candidate_tokens = tuple(
        sorted(
            token
            for token in ordered_tokens
            if token_active.get((normalized_auction, token)) is True
            or (balance_by_pair.get((normalized_auction, token)) or 0) > 0
            or (kicked_by_pair.get((normalized_auction, token)) or 0) > 0
        )
    )

    selected_token = normalized_token
    if selected_token is None and len(candidate_tokens) == 1:
        selected_token = candidate_tokens[0]

    selected_token_active = None
    selected_token_balance_raw = None
    selected_token_kicked_at = None
    if selected_token is not None:
        selected_token_active = token_active.get((normalized_auction, selected_token))
        selected_token_balance_raw = balance_by_pair.get((normalized_auction, selected_token))
        selected_token_kicked_at = kicked_by_pair.get((normalized_auction, selected_token))

    active_token = active_tokens[0] if len(active_tokens) == 1 else None
    inactive_token = (
        selected_token
        if selected_token is not None and selected_token_active is not True
        else None
    )

    return AuctionInspection(
        auction_address=normalized_auction,
        is_active_auction=is_active_auction,
        active_tokens=active_tokens,
        active_token=active_token,
        active_available_raw=selected_token_balance_raw if selected_token_active is True else None,
        enabled_tokens=tuple(sorted(enabled_tokens)),
        inactive_tokens_with_balance=inactive_tokens_with_balance,
        inactive_tokens_with_kick=inactive_tokens_with_kick,
        candidate_tokens=candidate_tokens,
        inactive_token=inactive_token,
        inactive_token_balance_raw=selected_token_balance_raw if inactive_token is not None else None,
        inactive_token_kicked_at=selected_token_kicked_at if inactive_token is not None else None,
        selected_token=selected_token,
        selected_token_active=selected_token_active,
        selected_token_balance_raw=selected_token_balance_raw,
        selected_token_kicked_at=selected_token_kicked_at,
    )


def decide_auction_settlement(
    inspection: AuctionInspection,
    *,
    token_address: str | None = None,
    method: SettlementMethod = "auto",
    allow_above_floor: bool = False,
) -> AuctionSettlementDecision:
    if allow_above_floor and method != "sweep_and_settle":
        raise ValueError("allow_above_floor requires method='sweep_and_settle'")

    forced = method in {"settle", "sweep_and_settle"}

    if inspection.is_active_auction is None:
        return AuctionSettlementDecision(
            status="error",
            operation_type=None,
            token_address=None,
            reason="auction isAnActiveAuction() read failed",
        )

    requested_token = normalize_address(token_address) if token_address is not None else None
    if requested_token is not None and requested_token not in inspection.candidate_tokens and inspection.candidate_tokens:
        if len(inspection.candidate_tokens) == 1:
            resolved_token = normalize_address(inspection.candidate_tokens[0])
            return AuctionSettlementDecision(
                status="error",
                operation_type=None,
                token_address=resolved_token,
                reason=(
                    f"requested token {to_checksum_address(requested_token)} does not match "
                    f"resolved token {to_checksum_address(resolved_token)}"
                ),
            )
        return AuctionSettlementDecision(
            status="error",
            operation_type=None,
            token_address=None,
            reason=f"requested token {to_checksum_address(requested_token)} is not a candidate token for this auction",
        )

    if inspection.selected_token is None:
        if len(inspection.candidate_tokens) > 1:
            return AuctionSettlementDecision(
                status="error",
                operation_type=None,
                token_address=None,
                reason="multiple candidate tokens detected for auction; pass --token",
            )
        return AuctionSettlementDecision(
            status="error" if forced else "noop",
            operation_type=None,
            token_address=None,
            reason=(
                "requested settlement method is not applicable: auction has nothing to resolve"
                if forced
                else "auction has nothing to resolve"
            ),
        )

    normalized_token = normalize_address(inspection.selected_token)
    active = inspection.selected_token_active is True
    balance_raw = inspection.selected_token_balance_raw or 0
    kicked_at = inspection.selected_token_kicked_at or 0

    if requested_token is not None and requested_token != normalized_token:
        return AuctionSettlementDecision(
            status="error",
            operation_type=None,
            token_address=normalized_token,
            reason=(
                f"requested token {to_checksum_address(requested_token)} does not match "
                f"resolved token {to_checksum_address(normalized_token)}"
            ),
        )

    if active:
        if balance_raw == 0:
            return AuctionSettlementDecision(
                status="actionable",
                operation_type="resolve_auction",
                token_address=normalized_token,
                reason="active lot is sold out",
            )
        if method == "settle":
            return AuctionSettlementDecision(
                status="error",
                operation_type=None,
                token_address=normalized_token,
                reason="settle is not applicable: active lot still has sell balance",
            )
        if allow_above_floor:
            return AuctionSettlementDecision(
                status="actionable",
                operation_type="resolve_auction",
                token_address=normalized_token,
                reason="forced sweep requested while auction is still active with sell balance",
            )
        return AuctionSettlementDecision(
            status="error" if forced else "noop",
            operation_type=None,
            token_address=normalized_token,
            reason=(
                "requested settlement method is not applicable: auction still active with sell balance"
                if forced
                else "auction still active with sell balance"
            ),
        )

    if kicked_at != 0:
        return AuctionSettlementDecision(
            status="actionable",
            operation_type="resolve_auction",
            token_address=normalized_token,
            reason=(
                "inactive kicked lot has stranded sell balance"
                if balance_raw > 0
                else "inactive kicked lot is stale and empty"
            ),
        )

    if balance_raw > 0:
        return AuctionSettlementDecision(
            status="actionable",
            operation_type="resolve_auction",
            token_address=normalized_token,
            reason="inactive lot holds sell balance",
        )

    return AuctionSettlementDecision(
        status="error" if forced else "noop",
        operation_type=None,
        token_address=normalized_token,
        reason=(
            "requested settlement method is not applicable: auction has nothing to resolve"
            if forced
            else "auction has nothing to resolve"
        ),
    )


def build_auction_settlement_call(
    *,
    settings,
    web3_client,
    auction_address: str,
    decision: AuctionSettlementDecision,
) -> AuctionSettlementCall:  # noqa: ANN001
    if decision.status != "actionable" or decision.operation_type is None or decision.token_address is None:
        raise ValueError("settlement call requires an actionable decision")

    normalized_auction = normalize_address(auction_address)
    normalized_token = normalize_address(decision.token_address)
    kicker_address = normalize_address(settings.auction_kicker_address)
    contract = web3_client.contract(kicker_address, AUCTION_KICKER_ABI)
    tx_data = contract.functions.resolveAuction(
        to_checksum_address(normalized_auction),
        to_checksum_address(normalized_token),
    )._encode_transaction_data()
    return AuctionSettlementCall(
        operation_type="resolve_auction",
        token_address=normalized_token,
        target_address=kicker_address,
        data=tx_data,
    )
