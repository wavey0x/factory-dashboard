from types import SimpleNamespace
from unittest.mock import MagicMock

from tidal.auction_settlement import (
    AuctionSettlementDecision,
    build_auction_settlement_call,
    decide_auction_settlement,
    normalize_settlement_method,
)
from tidal.transaction_service.types import AuctionInspection


def _make_inspection(**overrides) -> AuctionInspection:
    defaults = {
        "auction_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "is_active_auction": True,
        "active_tokens": ("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",),
        "active_token": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "candidate_tokens": ("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",),
        "selected_token": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "selected_token_active": True,
        "selected_token_balance_raw": 10**18,
        "selected_token_kicked_at": 123,
    }
    defaults.update(overrides)
    return AuctionInspection(**defaults)


def test_normalize_settlement_method_accepts_dash_form() -> None:
    assert normalize_settlement_method("sweep-and-settle") == "sweep_and_settle"


def test_decide_auction_settlement_no_candidate_is_noop_in_auto_mode() -> None:
    decision = decide_auction_settlement(
        _make_inspection(
            is_active_auction=False,
            active_tokens=(),
            active_token=None,
            candidate_tokens=(),
            selected_token=None,
            selected_token_active=None,
            selected_token_balance_raw=None,
            selected_token_kicked_at=None,
        )
    )

    assert decision.status == "noop"
    assert decision.operation_type is None
    assert decision.reason == "auction has nothing to resolve"


def test_decide_auction_settlement_no_candidate_is_error_for_forced_method() -> None:
    decision = decide_auction_settlement(
        _make_inspection(
            is_active_auction=False,
            active_tokens=(),
            active_token=None,
            candidate_tokens=(),
            selected_token=None,
            selected_token_active=None,
            selected_token_balance_raw=None,
            selected_token_kicked_at=None,
        ),
        method="settle",
    )

    assert decision.status == "error"
    assert decision.reason == "requested settlement method is not applicable: auction has nothing to resolve"


def test_decide_auction_settlement_multiple_candidates_requires_token() -> None:
    decision = decide_auction_settlement(
        _make_inspection(
            is_active_auction=False,
            active_tokens=(),
            active_token=None,
            candidate_tokens=(
                "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            ),
            selected_token=None,
            selected_token_active=None,
            selected_token_balance_raw=None,
            selected_token_kicked_at=None,
        )
    )

    assert decision.status == "error"
    assert decision.reason == "multiple candidate tokens detected for auction; pass --token"


def test_decide_auction_settlement_requested_token_mismatch_is_error() -> None:
    decision = decide_auction_settlement(
        _make_inspection(
            is_active_auction=False,
            active_tokens=(),
            active_token=None,
            candidate_tokens=("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",),
            selected_token="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            selected_token_active=False,
            selected_token_balance_raw=0,
            selected_token_kicked_at=0,
        ),
        token_address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    )

    assert decision.status == "error"
    assert decision.token_address == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert (
        decision.reason
        == "requested token 0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB does not match "
        "resolved token 0xaAaAaAaaAaAaAaaAaAAAAAAAAaaaAaAaAaaAaaAa"
    )


def test_decide_auction_settlement_active_sold_out_selects_resolver() -> None:
    decision = decide_auction_settlement(_make_inspection(selected_token_balance_raw=0))

    assert decision.status == "actionable"
    assert decision.operation_type == "resolve_auction"
    assert decision.token_address == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert decision.reason == "active lot is sold out"


def test_decide_auction_settlement_active_with_balance_is_noop_in_auto_mode() -> None:
    decision = decide_auction_settlement(_make_inspection(selected_token_balance_raw=10**18))

    assert decision.status == "noop"
    assert decision.operation_type is None
    assert decision.reason == "auction still active with sell balance"


def test_decide_auction_settlement_active_with_balance_is_error_for_settle() -> None:
    decision = decide_auction_settlement(
        _make_inspection(selected_token_balance_raw=10**18),
        method="settle",
    )

    assert decision.status == "error"
    assert decision.reason == "settle is not applicable: active lot still has sell balance"


def test_decide_auction_settlement_active_with_balance_forced_sweep_is_actionable() -> None:
    decision = decide_auction_settlement(
        _make_inspection(selected_token_balance_raw=10**18),
        method="sweep_and_settle",
        allow_above_floor=True,
    )

    assert decision.status == "actionable"
    assert decision.operation_type == "resolve_auction"
    assert decision.reason == "forced sweep requested while auction is still active with sell balance"


def test_decide_auction_settlement_inactive_kicked_with_balance_selects_resolver() -> None:
    decision = decide_auction_settlement(
        _make_inspection(
            is_active_auction=False,
            active_tokens=(),
            active_token=None,
            selected_token_active=False,
            selected_token_balance_raw=10**18,
            selected_token_kicked_at=123,
        )
    )

    assert decision.status == "actionable"
    assert decision.operation_type == "resolve_auction"
    assert decision.reason == "inactive kicked lot has stranded sell balance"


def test_decide_auction_settlement_inactive_kicked_empty_selects_resolver() -> None:
    decision = decide_auction_settlement(
        _make_inspection(
            is_active_auction=False,
            active_tokens=(),
            active_token=None,
            selected_token_active=False,
            selected_token_balance_raw=0,
            selected_token_kicked_at=123,
        )
    )

    assert decision.status == "actionable"
    assert decision.operation_type == "resolve_auction"
    assert decision.reason == "inactive kicked lot is stale and empty"


def test_decide_auction_settlement_inactive_clean_with_balance_selects_resolver() -> None:
    decision = decide_auction_settlement(
        _make_inspection(
            is_active_auction=False,
            active_tokens=(),
            active_token=None,
            selected_token_active=False,
            selected_token_balance_raw=10**18,
            selected_token_kicked_at=0,
        )
    )

    assert decision.status == "actionable"
    assert decision.operation_type == "resolve_auction"
    assert decision.reason == "inactive lot holds sell balance"


def test_build_auction_settlement_call_targets_kicker_resolver() -> None:
    mock_contract = MagicMock()
    mock_resolve = MagicMock()
    mock_resolve._encode_transaction_data.return_value = "0xfeedface"
    mock_contract.functions.resolveAuction.return_value = mock_resolve

    web3_client = MagicMock()
    web3_client.contract.return_value = mock_contract

    call = build_auction_settlement_call(
        settings=SimpleNamespace(auction_kicker_address="0x9999999999999999999999999999999999999999"),
        web3_client=web3_client,
        auction_address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        decision=AuctionSettlementDecision(
            status="actionable",
            operation_type="resolve_auction",
            token_address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            reason="inactive kicked lot has stranded sell balance",
        ),
    )

    assert call.operation_type == "resolve_auction"
    assert call.target_address == "0x9999999999999999999999999999999999999999"
    assert call.data == "0xfeedface"
