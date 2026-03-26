import pytest

from factory_dashboard.config import MonitoredFeeBurner
from factory_dashboard.ops.auction_enable import parse_manual_token_input, resolve_source_type


def test_parse_manual_token_input_normalizes_addresses() -> None:
    parsed = parse_manual_token_input(
        "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48, 0xD533a949740bb3306d119CC777fa900bA034cd52"
    )

    assert parsed == [
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "0xd533a949740bb3306d119cc777fa900ba034cd52",
    ]


def test_resolve_source_type_returns_fee_burner_with_warning() -> None:
    result = resolve_source_type(
        receiver="0xb911Fcce8D5AFCEc73E072653107260bb23C1eE8",
        auction_want="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        monitored_fee_burners=[
            MonitoredFeeBurner(
                address="0xb911Fcce8D5AFCEc73E072653107260bb23C1eE8",
                want_address="0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E",
                label="yCRV Fee Burner",
            )
        ],
        strategy_want=None,
    )

    assert result.source_type == "fee_burner"
    assert result.source_name == "yCRV Fee Burner"
    assert len(result.warnings) == 1


def test_resolve_source_type_returns_strategy_when_want_matches() -> None:
    result = resolve_source_type(
        receiver="0x9AD3047D578e79187f0FaEEf26729097a4973325",
        auction_want="0xf939e0a03fb07f59a73314e73794be0e57ac1b4e",
        monitored_fee_burners=[],
        strategy_want="0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E",
        strategy_name="Curve Strategy",
    )

    assert result.source_type == "strategy"
    assert result.source_address == "0x9ad3047d578e79187f0faeef26729097a4973325"
    assert result.source_name == "Curve Strategy"
    assert result.warnings == ()


def test_resolve_source_type_rejects_unknown_receiver() -> None:
    with pytest.raises(RuntimeError):
        resolve_source_type(
            receiver="0x9AD3047D578e79187f0FaEEf26729097a4973325",
            auction_want="0xf939e0a03fb07f59a73314e73794be0e57ac1b4e",
            monitored_fee_burners=[],
            strategy_want="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        )
