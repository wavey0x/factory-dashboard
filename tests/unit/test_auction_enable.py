from eth_abi import encode
import pytest

from tidal.config import MonitoredFeeBurner
from tidal.ops.auction_enable import (
    AuctionInspection,
    AuctionTokenEnabler,
    SourceResolution,
    TokenDiscovery,
    parse_manual_token_input,
    resolve_source_type,
)


class _FakeEnableFn:
    def __init__(self, data: str = "0xdeadbeef", call_error: Exception | None = None, gas_error: Exception | None = None) -> None:
        self._data = data
        self._call_error = call_error
        self._gas_error = gas_error

    def _encode_transaction_data(self) -> str:
        return self._data

    def call(self, tx: dict[str, str]) -> None:
        del tx
        if self._call_error is not None:
            raise self._call_error

    def build_transaction(self, tx: dict[str, str]) -> dict[str, str]:
        if self._gas_error is not None:
            raise self._gas_error
        return tx


class _FakeKickerFunctions:
    def __init__(self, owner: str, keepers: dict[str, bool], enable_fn: _FakeEnableFn) -> None:
        self._owner = owner
        self._keepers = keepers
        self._enable_fn = enable_fn

    def owner(self):
        owner = self._owner
        return type("_Call", (), {"call": lambda _self: owner})()

    def keeper(self, caller: str):
        keepers = self._keepers
        return type("_Call", (), {"call": lambda _self: keepers.get(caller.lower(), False)})()

    def enableTokens(self, auction: str, tokens: list[str]) -> _FakeEnableFn:
        del auction, tokens
        return self._enable_fn


class _FakeContract:
    def __init__(self, functions) -> None:  # noqa: ANN001
        self.functions = functions


class _FakeEth:
    def __init__(self, contract, gas_estimate: int) -> None:  # noqa: ANN001
        self._contract = contract
        self._gas_estimate = gas_estimate

    def contract(self, *, address: str, abi):  # noqa: ANN001
        del address, abi
        return self._contract

    def estimate_gas(self, tx: dict[str, str]) -> int:
        del tx
        return self._gas_estimate


class _FakeWeb3:
    def __init__(self, contract, gas_estimate: int = 210_000) -> None:  # noqa: ANN001
        self.eth = _FakeEth(contract, gas_estimate)


class _FakeAuctionStateCall:
    def __init__(self, token: str, direct_value: tuple[int, int, int] | None = None) -> None:
        self.token = token
        self.direct_value = direct_value

    def _encode_transaction_data(self) -> bytes:
        return f"auctions:{self.token}".encode()

    def call(self):
        if self.direct_value is None:
            raise RuntimeError("direct call unavailable")
        return self.direct_value


class _FakeAuctionStateFunctions:
    def __init__(self, direct_values: dict[str, tuple[int, int, int]] | None = None) -> None:
        self.direct_values = direct_values or {}
        self.direct_calls = 0

    def auctions(self, token: str) -> _FakeAuctionStateCall:
        normalized = token.lower()
        value = self.direct_values.get(normalized)
        call = _FakeAuctionStateCall(normalized, value)
        original_call = call.call

        def tracked_call():
            self.direct_calls += 1
            return original_call()

        call.call = tracked_call  # type: ignore[method-assign]
        return call


class _FakeAggregateCall:
    def __init__(self, calls: list[dict[str, object]], scalers_by_token: dict[str, int]) -> None:
        self.calls = calls
        self.scalers_by_token = scalers_by_token

    def call(self):
        output = []
        for item in self.calls:
            token = bytes(item["callData"]).decode().split(":", 1)[1].lower()
            scaler = self.scalers_by_token.get(token)
            if scaler is None:
                output.append((False, b""))
                continue
            output.append((True, encode(["uint64", "uint64", "uint128"], [0, scaler, 0])))
        return output


class _FakeMulticallFunctions:
    def __init__(self, scalers_by_token: dict[str, int]) -> None:
        self.scalers_by_token = scalers_by_token
        self.calls = 0

    def aggregate3(self, calls: list[dict[str, object]]) -> _FakeAggregateCall:
        self.calls += 1
        return _FakeAggregateCall(calls, self.scalers_by_token)


class _FakeEnabledEth:
    def __init__(self, *, auction_functions: _FakeAuctionStateFunctions, multicall_functions: _FakeMulticallFunctions) -> None:
        self.auction_functions = auction_functions
        self.multicall_functions = multicall_functions

    def contract(self, *, address: str, abi):  # noqa: ANN001
        del abi
        if address.lower() == "0xca11bde05977b3631167028862be2a173976ca11":
            return _FakeContract(self.multicall_functions)
        return _FakeContract(self.auction_functions)


class _FakeEnabledWeb3:
    def __init__(self, *, auction_functions: _FakeAuctionStateFunctions, multicall_functions: _FakeMulticallFunctions) -> None:
        self.eth = _FakeEnabledEth(
            auction_functions=auction_functions,
            multicall_functions=multicall_functions,
        )


def test_build_execution_plan_uses_auction_kicker_and_keeper_auth() -> None:
    enable_fn = _FakeEnableFn()
    contract = _FakeContract(
        _FakeKickerFunctions(
            owner="0x1111111111111111111111111111111111111111",
            keepers={"0x2222222222222222222222222222222222222222": True},
            enable_fn=enable_fn,
        )
    )
    enabler = AuctionTokenEnabler(
        _FakeWeb3(contract),
        type("Settings", (), {"auction_kicker_address": "0x3333333333333333333333333333333333333333"})(),
    )

    plan = enabler.build_execution_plan(
        inspection=AuctionInspection(
            auction_address="0x4444444444444444444444444444444444444444",
            governance="0xb634316e06cc0b358437cbadd4dc94f1d3a92b3b",
            want="0x5555555555555555555555555555555555555555",
            receiver="0x6666666666666666666666666666666666666666",
            version="1.0.0",
            in_configured_factory=True,
            governance_matches_required=True,
            enabled_tokens=(),
        ),
        tokens=["0x7777777777777777777777777777777777777777"],
        caller_address="0x2222222222222222222222222222222222222222",
    )

    assert plan.to_address == "0x3333333333333333333333333333333333333333"
    assert plan.data == "0xdeadbeef"
    assert plan.call_succeeded is True
    assert plan.gas_estimate == 210_000
    assert plan.sender_authorized is True
    assert plan.authorization_target == "0x3333333333333333333333333333333333333333"


def test_read_auction_token_enabled_many_uses_multicall_scaler() -> None:
    enabled_token = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    disabled_token = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    auction_functions = _FakeAuctionStateFunctions()
    multicall_functions = _FakeMulticallFunctions(
        {
            enabled_token: 10**18,
            disabled_token: 0,
        }
    )
    enabler = AuctionTokenEnabler(
        _FakeEnabledWeb3(
            auction_functions=auction_functions,
            multicall_functions=multicall_functions,
        ),
        type(
            "Settings",
            (),
            {
                "multicall_enabled": True,
                "multicall_address": "0xca11bde05977b3631167028862be2a173976ca11",
                "multicall_auction_batch_calls": 10,
            },
        )(),
    )

    result = enabler._read_auction_token_enabled_many(
        "0x1111111111111111111111111111111111111111",
        [enabled_token, disabled_token],
    )

    assert result == {
        enabled_token: True,
        disabled_token: False,
    }
    assert multicall_functions.calls == 1
    assert auction_functions.direct_calls == 0


def test_probe_tokens_skips_enabled_token_from_auction_state(monkeypatch) -> None:
    enabled_token = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    disabled_token = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    source_address = "0x3333333333333333333333333333333333333333"
    enabler = AuctionTokenEnabler(
        _FakeWeb3(_FakeContract(_FakeKickerFunctions(owner="0x1", keepers={}, enable_fn=_FakeEnableFn()))),
        type("Settings", (), {})(),
    )
    monkeypatch.setattr(
        enabler,
        "_read_auction_token_enabled_many",
        lambda auction_address, token_addresses: {
            enabled_token: True,
            disabled_token: False,
        },
    )
    monkeypatch.setattr(enabler, "_read_token_symbol", lambda token_address: "TOK")
    monkeypatch.setattr(enabler, "_read_token_decimals", lambda token_address: 18)
    monkeypatch.setattr(enabler, "_read_token_balance", lambda token_address, holder_address: 1)
    monkeypatch.setattr(
        enabler,
        "_auction_contract",
        lambda auction_address: _FakeContract(
            type("_Functions", (), {"enable": lambda _self, token: _FakeEnableFn()})()
        ),
    )

    probes = enabler.probe_tokens(
        inspection=AuctionInspection(
            auction_address="0x1111111111111111111111111111111111111111",
            governance="0xb634316e06cc0b358437cbadd4dc94f1d3a92b3b",
            want="0x2222222222222222222222222222222222222222",
            receiver=source_address,
            version="1.0.4",
            in_configured_factory=True,
            governance_matches_required=True,
            enabled_tokens=(),
        ),
        source=SourceResolution(
            source_type="fee_burner",
            source_address=source_address,
            source_name="Fee Burner",
        ),
        discovery=TokenDiscovery(
            tokens_by_address={
                enabled_token: {"manual"},
                disabled_token: {"manual"},
            },
            notes=[],
        ),
    )

    probes_by_token = {probe.token_address: probe for probe in probes}
    assert probes_by_token[enabled_token].status == "skip"
    assert probes_by_token[enabled_token].reason == "already_enabled"
    assert probes_by_token[disabled_token].status == "eligible"


def test_build_execution_plan_rejects_governance_mismatch() -> None:
    enabler = AuctionTokenEnabler(
        _FakeWeb3(_FakeContract(_FakeKickerFunctions(owner="0x1", keepers={}, enable_fn=_FakeEnableFn()))),
        type("Settings", (), {"auction_kicker_address": "0x3333333333333333333333333333333333333333"})(),
    )

    with pytest.raises(RuntimeError, match="standard Yearn auctions via AuctionKicker"):
        enabler.build_execution_plan(
            inspection=AuctionInspection(
                auction_address="0x4444444444444444444444444444444444444444",
                governance="0x9999999999999999999999999999999999999999",
                want="0x5555555555555555555555555555555555555555",
                receiver="0x6666666666666666666666666666666666666666",
                version="1.0.0",
                in_configured_factory=True,
                governance_matches_required=False,
                enabled_tokens=(),
            ),
            tokens=["0x7777777777777777777777777777777777777777"],
            caller_address="0x2222222222222222222222222222222222222222",
        )


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
