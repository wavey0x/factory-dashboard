"""Unit tests for AuctionKicker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from factory_dashboard.persistence import models
from factory_dashboard.persistence.repositories import KickTxRepository
from factory_dashboard.transaction_service.kicker import AuctionKicker, _DEFAULT_PRIORITY_FEE_GWEI
from factory_dashboard.transaction_service.types import KickCandidate


def _make_candidate(**overrides):
    defaults = {
        "strategy_address": "0x1111111111111111111111111111111111111111",
        "token_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "auction_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "normalized_balance": "1000",
        "price_usd": "2.5",
        "usd_value": 2500.0,
        "decimals": 18,
    }
    defaults.update(overrides)
    return KickCandidate(**defaults)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    models.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def kick_tx_repo(session):
    return KickTxRepository(session)


def _make_kicker(session, *, web3_client=None, signer=None, **overrides):
    if web3_client is None:
        web3_client = MagicMock()
    if signer is None:
        signer = MagicMock()
        signer.address = "0xcccccccccccccccccccccccccccccccccccccccc"
        signer.checksum_address = "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"

    kick_tx_repo = KickTxRepository(session)

    defaults = {
        "web3_client": web3_client,
        "signer": signer,
        "kick_tx_repository": kick_tx_repo,
        "usd_threshold": 100.0,
        "max_gas_price_gwei": 50,
        "max_priority_fee_gwei": 2,
        "max_gas_limit": 500000,
        "start_price_buffer_bps": 1000,
        "chain_id": 1,
    }
    defaults.update(overrides)
    return AuctionKicker(**defaults)


@pytest.mark.asyncio
async def test_kick_below_threshold_on_live_balance(session):
    """When live balance is below threshold, should return SKIP without persisting."""
    web3_client = MagicMock()

    with patch(
        "factory_dashboard.chain.contracts.erc20.ERC20Reader"
    ) as MockERC20:
        mock_erc20 = AsyncMock()
        # Return a tiny balance → USD value below threshold.
        mock_erc20.read_balance = AsyncMock(return_value=1000)  # 1000 wei ≈ 0
        MockERC20.return_value = mock_erc20

        kicker = _make_kicker(session, web3_client=web3_client)
        candidate = _make_candidate()
        result = await kicker.kick(candidate, "run-1")

    assert result.status == "SKIP"
    # No kick_txs row should be written for SKIP.
    rows = session.execute(select(models.kick_txs)).mappings().all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_kick_balance_read_error(session):
    """When balance read fails, should persist ERROR row."""
    web3_client = MagicMock()

    with patch(
        "factory_dashboard.chain.contracts.erc20.ERC20Reader"
    ) as MockERC20:
        mock_erc20 = AsyncMock()
        mock_erc20.read_balance = AsyncMock(side_effect=RuntimeError("rpc down"))
        MockERC20.return_value = mock_erc20

        kicker = _make_kicker(session, web3_client=web3_client)
        candidate = _make_candidate()
        result = await kicker.kick(candidate, "run-1")

    assert result.status == "ERROR"
    assert "rpc down" in result.error_message
    rows = session.execute(select(models.kick_txs)).mappings().all()
    assert len(rows) == 1
    assert rows[0]["status"] == "ERROR"
    assert "balance read failed" in rows[0]["error_message"]


@pytest.mark.asyncio
async def test_kick_gas_price_too_high(session):
    """When gas price exceeds ceiling, should persist ERROR."""
    web3_client = MagicMock()
    web3_client.get_balance = AsyncMock(return_value=int(1 * 1e18))  # 1 ETH
    web3_client.get_gas_price = AsyncMock(return_value=int(100 * 1e9))  # 100 gwei

    with patch(
        "factory_dashboard.chain.contracts.erc20.ERC20Reader"
    ) as MockERC20:
        mock_erc20 = AsyncMock()
        mock_erc20.read_balance = AsyncMock(return_value=10**21)
        MockERC20.return_value = mock_erc20

        kicker = _make_kicker(session, web3_client=web3_client, max_gas_price_gwei=50)
        candidate = _make_candidate()
        result = await kicker.kick(candidate, "run-1")

    assert result.status == "ERROR"
    assert "gas price too high" in result.error_message


@pytest.mark.asyncio
async def test_kick_estimate_failed(session):
    """When estimateGas fails, should persist ESTIMATE_FAILED."""
    web3_client = MagicMock()
    web3_client.get_balance = AsyncMock(return_value=int(1 * 1e18))
    web3_client.get_gas_price = AsyncMock(return_value=int(10 * 1e9))

    mock_contract = MagicMock()
    mock_kick_fn = MagicMock()
    mock_kick_fn._encode_transaction_data = MagicMock(return_value="0xdeadbeef")
    mock_contract.functions.kick = MagicMock(return_value=mock_kick_fn)
    web3_client.contract = MagicMock(return_value=mock_contract)
    web3_client.estimate_gas = AsyncMock(side_effect=RuntimeError("execution reverted"))

    with patch(
        "factory_dashboard.chain.contracts.erc20.ERC20Reader"
    ) as MockERC20:
        mock_erc20 = AsyncMock()
        mock_erc20.read_balance = AsyncMock(return_value=10**21)
        MockERC20.return_value = mock_erc20

        kicker = _make_kicker(session, web3_client=web3_client)
        candidate = _make_candidate()
        result = await kicker.kick(candidate, "run-1")

    assert result.status == "ESTIMATE_FAILED"
    rows = session.execute(select(models.kick_txs)).mappings().all()
    assert len(rows) == 1
    assert rows[0]["status"] == "ESTIMATE_FAILED"


@pytest.mark.asyncio
async def test_kick_gas_estimate_over_cap(session):
    """When gas estimate exceeds max_gas_limit, should persist ERROR."""
    web3_client = MagicMock()
    web3_client.get_balance = AsyncMock(return_value=int(1 * 1e18))
    web3_client.get_gas_price = AsyncMock(return_value=int(10 * 1e9))

    mock_contract = MagicMock()
    mock_kick_fn = MagicMock()
    mock_kick_fn._encode_transaction_data = MagicMock(return_value="0xdeadbeef")
    mock_contract.functions.kick = MagicMock(return_value=mock_kick_fn)
    web3_client.contract = MagicMock(return_value=mock_contract)
    web3_client.estimate_gas = AsyncMock(return_value=600000)  # exceeds 500000 cap

    with patch(
        "factory_dashboard.chain.contracts.erc20.ERC20Reader"
    ) as MockERC20:
        mock_erc20 = AsyncMock()
        mock_erc20.read_balance = AsyncMock(return_value=10**21)
        MockERC20.return_value = mock_erc20

        kicker = _make_kicker(session, web3_client=web3_client)
        candidate = _make_candidate()
        result = await kicker.kick(candidate, "run-1")

    assert result.status == "ERROR"
    assert "gas estimate" in result.error_message


@pytest.mark.asyncio
async def test_kick_confirmed(session):
    """Full happy path: estimate → sign → send → receipt confirmed."""
    web3_client = MagicMock()
    web3_client.get_balance = AsyncMock(return_value=int(1 * 1e18))
    web3_client.get_gas_price = AsyncMock(return_value=int(10 * 1e9))
    web3_client.get_max_priority_fee = AsyncMock(return_value=int(0.05 * 1e9))
    web3_client.estimate_gas = AsyncMock(return_value=200000)
    web3_client.get_transaction_count = AsyncMock(return_value=5)
    web3_client.send_raw_transaction = AsyncMock(return_value="0xtxhash123")
    web3_client.get_transaction_receipt = AsyncMock(return_value={
        "status": 1,
        "gasUsed": 180000,
        "effectiveGasPrice": int(12 * 1e9),
        "blockNumber": 12345,
    })

    mock_contract = MagicMock()
    mock_kick_fn = MagicMock()
    mock_kick_fn._encode_transaction_data = MagicMock(return_value="0xdeadbeef")
    mock_contract.functions.kick = MagicMock(return_value=mock_kick_fn)
    web3_client.contract = MagicMock(return_value=mock_contract)

    signer = MagicMock()
    signer.address = "0xcccccccccccccccccccccccccccccccccccccccc"
    signer.checksum_address = "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
    signer.sign_transaction = MagicMock(return_value=b"\x00" * 32)

    with patch(
        "factory_dashboard.chain.contracts.erc20.ERC20Reader"
    ) as MockERC20:
        mock_erc20 = AsyncMock()
        mock_erc20.read_balance = AsyncMock(return_value=10**21)
        MockERC20.return_value = mock_erc20

        kicker = _make_kicker(session, web3_client=web3_client, signer=signer)
        candidate = _make_candidate()
        result = await kicker.kick(candidate, "run-1")

    assert result.status == "CONFIRMED"
    assert result.tx_hash == "0xtxhash123"
    assert result.gas_used == 180000
    assert result.block_number == 12345

    rows = session.execute(select(models.kick_txs)).mappings().all()
    assert len(rows) == 1
    assert rows[0]["status"] == "CONFIRMED"
    assert rows[0]["tx_hash"] == "0xtxhash123"


@pytest.mark.asyncio
async def test_kick_reverted(session):
    """Receipt shows reverted → status should be REVERTED."""
    web3_client = MagicMock()
    web3_client.get_balance = AsyncMock(return_value=int(1 * 1e18))
    web3_client.get_gas_price = AsyncMock(return_value=int(10 * 1e9))
    web3_client.get_max_priority_fee = AsyncMock(return_value=int(0.05 * 1e9))
    web3_client.estimate_gas = AsyncMock(return_value=200000)
    web3_client.get_transaction_count = AsyncMock(return_value=5)
    web3_client.send_raw_transaction = AsyncMock(return_value="0xtxhash456")
    web3_client.get_transaction_receipt = AsyncMock(return_value={
        "status": 0,
        "gasUsed": 150000,
        "effectiveGasPrice": int(12 * 1e9),
        "blockNumber": 12346,
    })

    mock_contract = MagicMock()
    mock_kick_fn = MagicMock()
    mock_kick_fn._encode_transaction_data = MagicMock(return_value="0xdeadbeef")
    mock_contract.functions.kick = MagicMock(return_value=mock_kick_fn)
    web3_client.contract = MagicMock(return_value=mock_contract)

    signer = MagicMock()
    signer.address = "0xcccccccccccccccccccccccccccccccccccccccc"
    signer.checksum_address = "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
    signer.sign_transaction = MagicMock(return_value=b"\x00" * 32)

    with patch(
        "factory_dashboard.chain.contracts.erc20.ERC20Reader"
    ) as MockERC20:
        mock_erc20 = AsyncMock()
        mock_erc20.read_balance = AsyncMock(return_value=10**21)
        MockERC20.return_value = mock_erc20

        kicker = _make_kicker(session, web3_client=web3_client, signer=signer)
        candidate = _make_candidate()
        result = await kicker.kick(candidate, "run-1")

    assert result.status == "REVERTED"
    rows = session.execute(select(models.kick_txs)).mappings().all()
    assert rows[0]["status"] == "REVERTED"


@pytest.mark.asyncio
async def test_kick_receipt_timeout_stays_submitted(session):
    """When receipt times out, row stays SUBMITTED."""
    web3_client = MagicMock()
    web3_client.get_balance = AsyncMock(return_value=int(1 * 1e18))
    web3_client.get_gas_price = AsyncMock(return_value=int(10 * 1e9))
    web3_client.get_max_priority_fee = AsyncMock(return_value=int(0.05 * 1e9))
    web3_client.estimate_gas = AsyncMock(return_value=200000)
    web3_client.get_transaction_count = AsyncMock(return_value=5)
    web3_client.send_raw_transaction = AsyncMock(return_value="0xtxhash789")
    web3_client.get_transaction_receipt = AsyncMock(side_effect=TimeoutError("receipt timeout"))

    mock_contract = MagicMock()
    mock_kick_fn = MagicMock()
    mock_kick_fn._encode_transaction_data = MagicMock(return_value="0xdeadbeef")
    mock_contract.functions.kick = MagicMock(return_value=mock_kick_fn)
    web3_client.contract = MagicMock(return_value=mock_contract)

    signer = MagicMock()
    signer.address = "0xcccccccccccccccccccccccccccccccccccccccc"
    signer.checksum_address = "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
    signer.sign_transaction = MagicMock(return_value=b"\x00" * 32)

    with patch(
        "factory_dashboard.chain.contracts.erc20.ERC20Reader"
    ) as MockERC20:
        mock_erc20 = AsyncMock()
        mock_erc20.read_balance = AsyncMock(return_value=10**21)
        MockERC20.return_value = mock_erc20

        kicker = _make_kicker(session, web3_client=web3_client, signer=signer)
        candidate = _make_candidate()
        result = await kicker.kick(candidate, "run-1")

    assert result.status == "SUBMITTED"
    assert result.tx_hash == "0xtxhash789"
    rows = session.execute(select(models.kick_txs)).mappings().all()
    assert len(rows) == 1
    assert rows[0]["status"] == "SUBMITTED"
    assert rows[0]["tx_hash"] == "0xtxhash789"


def _make_web3_client_through_gas_estimate(gas_estimate=200000):
    """Build a mock web3_client that passes all checks up through gas estimation."""
    web3_client = MagicMock()
    web3_client.get_balance = AsyncMock(return_value=int(1 * 1e18))
    web3_client.get_gas_price = AsyncMock(return_value=int(10 * 1e9))
    web3_client.get_max_priority_fee = AsyncMock(return_value=int(0.05 * 1e9))
    web3_client.estimate_gas = AsyncMock(return_value=gas_estimate)

    mock_contract = MagicMock()
    mock_kick_fn = MagicMock()
    mock_kick_fn._encode_transaction_data = MagicMock(return_value="0xdeadbeef")
    mock_contract.functions.kick = MagicMock(return_value=mock_kick_fn)
    web3_client.contract = MagicMock(return_value=mock_contract)
    return web3_client


@pytest.mark.asyncio
async def test_kick_confirm_fn_declined(session):
    """When confirm_fn returns False, should persist USER_SKIPPED and not send."""
    web3_client = _make_web3_client_through_gas_estimate()

    confirm_fn = MagicMock(return_value=False)

    with patch(
        "factory_dashboard.chain.contracts.erc20.ERC20Reader"
    ) as MockERC20:
        mock_erc20 = AsyncMock()
        mock_erc20.read_balance = AsyncMock(return_value=10**21)
        MockERC20.return_value = mock_erc20

        kicker = _make_kicker(session, web3_client=web3_client, confirm_fn=confirm_fn)
        candidate = _make_candidate()
        result = await kicker.kick(candidate, "run-1")

    assert result.status == "USER_SKIPPED"
    assert result.sell_amount is not None
    assert result.usd_value is not None

    # confirm_fn should have been called with a summary dict.
    confirm_fn.assert_called_once()
    summary = confirm_fn.call_args[0][0]
    assert "strategy" in summary
    assert "gas_estimate" in summary
    assert "gas_limit" in summary
    assert "buffer_bps" in summary
    assert isinstance(summary["buffer_bps"], int)

    # Should NOT have tried to send.
    web3_client.get_transaction_count.assert_not_called()
    web3_client.send_raw_transaction.assert_not_called()

    rows = session.execute(select(models.kick_txs)).mappings().all()
    assert len(rows) == 1
    assert rows[0]["status"] == "USER_SKIPPED"


@pytest.mark.asyncio
async def test_kick_confirm_fn_accepted(session):
    """When confirm_fn returns True, should proceed to sign and send."""
    web3_client = _make_web3_client_through_gas_estimate()
    web3_client.get_transaction_count = AsyncMock(return_value=5)
    web3_client.send_raw_transaction = AsyncMock(return_value="0xtxhash_confirmed")
    web3_client.get_transaction_receipt = AsyncMock(return_value={
        "status": 1,
        "gasUsed": 180000,
        "effectiveGasPrice": int(12 * 1e9),
        "blockNumber": 99999,
    })

    signer = MagicMock()
    signer.address = "0xcccccccccccccccccccccccccccccccccccccccc"
    signer.checksum_address = "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
    signer.sign_transaction = MagicMock(return_value=b"\x00" * 32)

    confirm_fn = MagicMock(return_value=True)

    with patch(
        "factory_dashboard.chain.contracts.erc20.ERC20Reader"
    ) as MockERC20:
        mock_erc20 = AsyncMock()
        mock_erc20.read_balance = AsyncMock(return_value=10**21)
        MockERC20.return_value = mock_erc20

        kicker = _make_kicker(session, web3_client=web3_client, signer=signer, confirm_fn=confirm_fn)
        candidate = _make_candidate()
        result = await kicker.kick(candidate, "run-1")

    assert result.status == "CONFIRMED"
    assert result.tx_hash == "0xtxhash_confirmed"
    confirm_fn.assert_called_once()


@pytest.mark.asyncio
async def test_kick_no_confirm_fn_sends_without_prompt(session):
    """When confirm_fn is None (default), should send without prompting."""
    web3_client = _make_web3_client_through_gas_estimate()
    web3_client.get_transaction_count = AsyncMock(return_value=5)
    web3_client.send_raw_transaction = AsyncMock(return_value="0xtxhash_no_confirm")
    web3_client.get_transaction_receipt = AsyncMock(return_value={
        "status": 1,
        "gasUsed": 180000,
        "effectiveGasPrice": int(12 * 1e9),
        "blockNumber": 99999,
    })

    signer = MagicMock()
    signer.address = "0xcccccccccccccccccccccccccccccccccccccccc"
    signer.checksum_address = "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
    signer.sign_transaction = MagicMock(return_value=b"\x00" * 32)

    with patch(
        "factory_dashboard.chain.contracts.erc20.ERC20Reader"
    ) as MockERC20:
        mock_erc20 = AsyncMock()
        mock_erc20.read_balance = AsyncMock(return_value=10**21)
        MockERC20.return_value = mock_erc20

        kicker = _make_kicker(session, web3_client=web3_client, signer=signer)
        candidate = _make_candidate()
        result = await kicker.kick(candidate, "run-1")

    assert result.status == "CONFIRMED"


# ---------------------------------------------------------------------------
# Priority fee resolution tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_priority_fee_uses_network_suggestion_below_cap(session):
    """When the network-suggested priority fee is below the cap, use it."""
    web3_client = _make_web3_client_through_gas_estimate()
    web3_client.get_max_priority_fee = AsyncMock(return_value=int(0.03 * 1e9))  # 0.03 gwei
    web3_client.get_transaction_count = AsyncMock(return_value=5)
    web3_client.send_raw_transaction = AsyncMock(return_value="0xtxhash_low_fee")
    web3_client.get_transaction_receipt = AsyncMock(return_value={
        "status": 1,
        "gasUsed": 180000,
        "effectiveGasPrice": int(12 * 1e9),
        "blockNumber": 55555,
    })

    signer = MagicMock()
    signer.address = "0xcccccccccccccccccccccccccccccccccccccccc"
    signer.checksum_address = "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
    signer.sign_transaction = MagicMock(return_value=b"\x00" * 32)

    with patch(
        "factory_dashboard.chain.contracts.erc20.ERC20Reader"
    ) as MockERC20:
        mock_erc20 = AsyncMock()
        mock_erc20.read_balance = AsyncMock(return_value=10**21)
        MockERC20.return_value = mock_erc20

        kicker = _make_kicker(session, web3_client=web3_client, signer=signer, max_priority_fee_gwei=2)
        candidate = _make_candidate()
        result = await kicker.kick(candidate, "run-1")

    assert result.status == "CONFIRMED"
    # The signed tx should use the network suggestion (0.03 gwei), not the cap (2 gwei).
    signed_tx_args = signer.sign_transaction.call_args[0][0]
    assert signed_tx_args["maxPriorityFeePerGas"] == int(0.03 * 1e9)


@pytest.mark.asyncio
async def test_priority_fee_capped_when_network_exceeds(session):
    """When the network-suggested priority fee exceeds the cap, use the cap."""
    web3_client = _make_web3_client_through_gas_estimate()
    web3_client.get_max_priority_fee = AsyncMock(return_value=int(5 * 1e9))  # 5 gwei > 2 gwei cap
    web3_client.get_transaction_count = AsyncMock(return_value=5)
    web3_client.send_raw_transaction = AsyncMock(return_value="0xtxhash_capped")
    web3_client.get_transaction_receipt = AsyncMock(return_value={
        "status": 1,
        "gasUsed": 180000,
        "effectiveGasPrice": int(12 * 1e9),
        "blockNumber": 55556,
    })

    signer = MagicMock()
    signer.address = "0xcccccccccccccccccccccccccccccccccccccccc"
    signer.checksum_address = "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
    signer.sign_transaction = MagicMock(return_value=b"\x00" * 32)

    with patch(
        "factory_dashboard.chain.contracts.erc20.ERC20Reader"
    ) as MockERC20:
        mock_erc20 = AsyncMock()
        mock_erc20.read_balance = AsyncMock(return_value=10**21)
        MockERC20.return_value = mock_erc20

        kicker = _make_kicker(session, web3_client=web3_client, signer=signer, max_priority_fee_gwei=2)
        candidate = _make_candidate()
        result = await kicker.kick(candidate, "run-1")

    assert result.status == "CONFIRMED"
    signed_tx_args = signer.sign_transaction.call_args[0][0]
    assert signed_tx_args["maxPriorityFeePerGas"] == 2 * 10**9


@pytest.mark.asyncio
async def test_priority_fee_fallback_on_rpc_failure(session):
    """When the RPC call for max_priority_fee fails, fall back to default."""
    web3_client = _make_web3_client_through_gas_estimate()
    web3_client.get_max_priority_fee = AsyncMock(side_effect=RuntimeError("rpc error"))
    web3_client.get_transaction_count = AsyncMock(return_value=5)
    web3_client.send_raw_transaction = AsyncMock(return_value="0xtxhash_fallback")
    web3_client.get_transaction_receipt = AsyncMock(return_value={
        "status": 1,
        "gasUsed": 180000,
        "effectiveGasPrice": int(12 * 1e9),
        "blockNumber": 55557,
    })

    signer = MagicMock()
    signer.address = "0xcccccccccccccccccccccccccccccccccccccccc"
    signer.checksum_address = "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
    signer.sign_transaction = MagicMock(return_value=b"\x00" * 32)

    with patch(
        "factory_dashboard.chain.contracts.erc20.ERC20Reader"
    ) as MockERC20:
        mock_erc20 = AsyncMock()
        mock_erc20.read_balance = AsyncMock(return_value=10**21)
        MockERC20.return_value = mock_erc20

        kicker = _make_kicker(session, web3_client=web3_client, signer=signer, max_priority_fee_gwei=2)
        candidate = _make_candidate()
        result = await kicker.kick(candidate, "run-1")

    assert result.status == "CONFIRMED"
    signed_tx_args = signer.sign_transaction.call_args[0][0]
    assert signed_tx_args["maxPriorityFeePerGas"] == int(_DEFAULT_PRIORITY_FEE_GWEI * 1e9)
