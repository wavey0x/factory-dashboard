"""Unit tests for scanner-side auction settlement."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from eth_abi import encode
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from tidal.persistence import models
from tidal.persistence.repositories import KickTxRepository
from tidal.scanner.auction_settler import AuctionSettlementService, AuctionSource
from tidal.transaction_service.signer import TransactionSigner
from tidal.types import TokenMetadata


class _FakeFunction:
    def __init__(self, name: str, args: tuple[object, ...] = ()) -> None:
        self.name = name
        self.args = args

    def _encode_transaction_data(self) -> bytes:
        return f"{self.name}:{','.join(map(str, self.args))}".encode()


class _FakeFunctions:
    def isAnActiveAuction(self):
        return _FakeFunction("isAnActiveAuction")

    def getAllEnabledAuctions(self):
        return _FakeFunction("getAllEnabledAuctions")

    def auctionLength(self):
        return _FakeFunction("auctionLength")

    def isActive(self, token):
        return _FakeFunction("isActive", (token,))

    def kicked(self, token):
        return _FakeFunction("kicked", (token,))

    def settle(self, token):
        return _FakeFunction("settle", (token,))


class _FakeContract:
    def __init__(self) -> None:
        self.functions = _FakeFunctions()


class _FakeWeb3Client:
    def __init__(self, *, estimate_error: Exception | None = None) -> None:
        self.estimate_error = estimate_error
        self.sent = 0

    def contract(self, address, abi):  # noqa: ARG002
        return _FakeContract()

    async def get_base_fee(self) -> int:
        return int(0.1 * 1e9)

    async def get_max_priority_fee(self) -> int:
        return int(1 * 1e9)

    async def get_transaction_count(self, address):  # noqa: ARG002
        return 7

    async def estimate_gas(self, tx):  # noqa: ARG002
        if self.estimate_error is not None:
            raise self.estimate_error
        return 100_000

    async def send_raw_transaction(self, signed_tx):  # noqa: ARG002
        self.sent += 1
        return "0xsettlehash"

    async def get_transaction_receipt(self, tx_hash, *, timeout_seconds=120):  # noqa: ARG002
        return {
            "status": 1,
            "gasUsed": 123456,
            "effectiveGasPrice": 300000000,
            "blockNumber": 999,
        }

    async def call(self, call_fn, **call_kwargs):  # noqa: ARG002
        if getattr(call_fn, "name", None) == "isAnActiveAuction":
            return True
        raise AssertionError("unexpected direct web3 call in test")


class _FakeMulticallClient:
    def __init__(self, values):
        self.values = values
        self.last_stats = SimpleNamespace(
            batch_count=1,
            subcalls_total=0,
            subcalls_failed=0,
            fallback_direct_calls_total=0,
        )

    async def execute(self, requests, *, batch_size, allow_failure=True, block="latest"):  # noqa: ARG002
        results = []
        for request in requests:
            value = self.values.get(request.logical_key)
            if value is None:
                results.append(SimpleNamespace(logical_key=request.logical_key, success=False, return_data=b""))
                continue
            results.append(SimpleNamespace(logical_key=request.logical_key, success=True, return_data=value))
        self.last_stats.subcalls_total = len(requests)
        return results


class _FakeERC20Reader:
    def __init__(self, balances):
        self.balances = balances

    async def read_balances_many(self, pairs):
        return ({pair: self.balances.get(pair) for pair in pairs}, {})


class _FakeTokenMetadataService:
    async def get_or_fetch(self, token_address, is_core_reward=False):  # noqa: ARG002
        token = token_address.lower()
        symbol = {
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": "OPASF",
            "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb": "crvUSD",
        }.get(token, "UNK")
        now = datetime.now(timezone.utc).isoformat()
        return TokenMetadata(
            address=token,
            chain_id=1,
            name=symbol,
            symbol=symbol,
            decimals=18,
            is_core_reward=False,
            first_seen_at=now,
            last_seen_at=now,
        )


class _FakeSigner:
    address = "0xcccccccccccccccccccccccccccccccccccccccc"
    checksum_address = "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"

    def sign_transaction(self, tx):  # noqa: ARG002
        return b"signed"


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    models.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_settler(session, *, web3_client, balances, multicall_values):
    return AuctionSettlementService(
        web3_client=web3_client,
        multicall_client=_FakeMulticallClient(multicall_values),
        multicall_enabled=True,
        multicall_auction_batch_calls=100,
        erc20_reader=_FakeERC20Reader(balances),
        signer=_FakeSigner(),
        kick_tx_repository=KickTxRepository(session),
        token_metadata_service=_FakeTokenMetadataService(),
        max_base_fee_gwei=0.5,
        max_priority_fee_gwei=2,
        max_gas_limit=500000,
        chain_id=1,
    )


def _settlement_values(*, auction, token):
    return {
        (auction, "isAnActiveAuction"): encode(["bool"], [True]),
        (auction, "getAllEnabledAuctions"): encode(["address[]"], [[token]]),
        (auction, "auctionLength"): encode(["uint256"], [86400]),
        (auction, token, "isActive"): encode(["bool"], [True]),
        (auction, token, "kicked"): encode(["uint256"], [1774497215]),
    }


@pytest.mark.asyncio
async def test_settler_confirms_zero_balance_settlement(session):
    auction = "0x1111111111111111111111111111111111111111"
    token = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    want = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    web3_client = _FakeWeb3Client()
    settler = _make_settler(
        session,
        web3_client=web3_client,
        balances={(auction, token): 0},
        multicall_values=_settlement_values(auction=auction, token=token),
    )

    result = await settler.settle_stale_auctions(
        run_id="run-1",
        sources=[AuctionSource("fee_burner", "0xburner", auction, want)],
    )

    assert result.stats.eligible_tokens == 1
    assert result.stats.settlements_attempted == 1
    assert result.stats.settlements_confirmed == 1
    rows = session.execute(select(models.kick_txs)).mappings().all()
    assert len(rows) == 1
    assert rows[0]["operation_type"] == "settle"
    assert rows[0]["status"] == "CONFIRMED"
    assert rows[0]["token_symbol"] == "OPASF"
    assert rows[0]["want_symbol"] == "crvUSD"


@pytest.mark.asyncio
async def test_settler_skips_nonzero_balance_blocker(session):
    auction = "0x1111111111111111111111111111111111111111"
    token = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    web3_client = _FakeWeb3Client()
    settler = _make_settler(
        session,
        web3_client=web3_client,
        balances={(auction, token): 123},
        multicall_values=_settlement_values(auction=auction, token=token),
    )

    result = await settler.settle_stale_auctions(
        run_id="run-1",
        sources=[AuctionSource("fee_burner", "0xburner", auction, "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")],
    )

    assert result.stats.blocking_tokens == 1
    assert result.stats.settlements_attempted == 0
    rows = session.execute(select(models.kick_txs)).mappings().all()
    assert rows == []


@pytest.mark.asyncio
async def test_settler_persists_estimate_failure(session):
    auction = "0x1111111111111111111111111111111111111111"
    token = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    web3_client = _FakeWeb3Client(estimate_error=RuntimeError("execution reverted: unauthorized"))
    settler = _make_settler(
        session,
        web3_client=web3_client,
        balances={(auction, token): 0},
        multicall_values=_settlement_values(auction=auction, token=token),
    )

    result = await settler.settle_stale_auctions(
        run_id="run-1",
        sources=[AuctionSource("fee_burner", "0xburner", auction, "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")],
    )

    assert len(result.errors) == 1
    assert result.errors[0].error_code == "auction_settlement_estimate_failed"
    rows = session.execute(select(models.kick_txs)).mappings().all()
    assert len(rows) == 1
    assert rows[0]["operation_type"] == "settle"
    assert rows[0]["status"] == "ESTIMATE_FAILED"
    assert rows[0]["error_message"] == "unauthorized"
