from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import Session

from tidal.auctionscan import AuctionScanService
from tidal.config import Settings
from tidal.persistence import models


def _insert_kick(
    session: Session,
    *,
    run_id: str,
    token_address: str,
    auction_address: str,
    status: str,
    tx_hash: str,
    created_at: str,
    auctionscan_last_checked_at: str | None = None,
) -> int:
    result = session.execute(
        insert(models.kick_txs).values(
            run_id=run_id,
            operation_type="kick",
            source_type="strategy",
            source_address="0x1111111111111111111111111111111111111111",
            strategy_address="0x1111111111111111111111111111111111111111",
            token_address=token_address,
            auction_address=auction_address,
            status=status,
            tx_hash=tx_hash,
            created_at=created_at,
            auctionscan_last_checked_at=auctionscan_last_checked_at,
        )
    )
    session.commit()
    return int(result.lastrowid)


@pytest.mark.asyncio
async def test_enrich_pending_kicks_persists_round_match(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    models.metadata.create_all(engine)

    with Session(engine) as session:
        service = AuctionScanService(session, Settings(chain_id=1, auctionscan_recheck_seconds=90))
        stale_checked_at = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        resolved_kick_id = _insert_kick(
            session,
            run_id="run-1",
            token_address="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            auction_address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            status="CONFIRMED",
            tx_hash="0x1111",
            created_at="2026-04-04T11:00:00+00:00",
        )
        recent_checked_at = datetime.now(timezone.utc).isoformat()
        skipped_kick_id = _insert_kick(
            session,
            run_id="run-2",
            token_address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            auction_address="0xcccccccccccccccccccccccccccccccccccccccc",
            status="CONFIRMED",
            tx_hash="0x2222",
            created_at="2026-04-04T10:00:00+00:00",
            auctionscan_last_checked_at=recent_checked_at,
        )
        _insert_kick(
            session,
            run_id="run-3",
            token_address="0xdddddddddddddddddddddddddddddddddddddddd",
            auction_address="0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            status="REVERTED",
            tx_hash="0x3333",
            created_at="2026-04-04T09:00:00+00:00",
            auctionscan_last_checked_at=stale_checked_at,
        )

        async def fake_lookup_round(*, auction_address: str, from_token: str, transaction_hash: str):
            assert auction_address == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            assert from_token == "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
            assert transaction_hash == "0x1111"
            return {"round_id": 42}

        monkeypatch.setattr(service, "_lookup_round", fake_lookup_round)

        result = await service.enrich_pending_kicks(limit=5)

        assert result.candidates_seen == 1
        assert result.kicks_checked == 1
        assert result.kicks_resolved == 1
        assert result.kicks_unresolved == 0
        assert result.kicks_failed == 0

        rows = session.execute(
            select(models.kick_txs).order_by(models.kick_txs.c.id.asc())
        ).mappings().all()
        rows_by_id = {row["id"]: row for row in rows}
        assert rows_by_id[resolved_kick_id]["auctionscan_round_id"] == 42
        assert rows_by_id[resolved_kick_id]["auctionscan_last_checked_at"] is not None
        assert rows_by_id[resolved_kick_id]["auctionscan_matched_at"] is not None
        assert rows_by_id[skipped_kick_id]["auctionscan_round_id"] is None
        assert rows_by_id[skipped_kick_id]["auctionscan_last_checked_at"] == recent_checked_at


@pytest.mark.asyncio
async def test_enrich_pending_kicks_records_checks_and_continues_on_errors(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    models.metadata.create_all(engine)

    with Session(engine) as session:
        service = AuctionScanService(session, Settings(chain_id=1, auctionscan_recheck_seconds=90))
        unresolved_kick_id = _insert_kick(
            session,
            run_id="run-1",
            token_address="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            auction_address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            status="CONFIRMED",
            tx_hash="0x1111",
            created_at="2026-04-04T11:00:00+00:00",
        )
        failed_kick_id = _insert_kick(
            session,
            run_id="run-2",
            token_address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            auction_address="0xcccccccccccccccccccccccccccccccccccccccc",
            status="CONFIRMED",
            tx_hash="0x2222",
            created_at="2026-04-04T10:00:00+00:00",
        )

        async def fake_lookup_round(*, auction_address: str, from_token: str, transaction_hash: str):
            del from_token
            if transaction_hash == "0x1111":
                return None
            raise RuntimeError(f"lookup failed for {auction_address}")

        monkeypatch.setattr(service, "_lookup_round", fake_lookup_round)

        result = await service.enrich_pending_kicks(limit=5)

        assert result.candidates_seen == 2
        assert result.kicks_checked == 1
        assert result.kicks_resolved == 0
        assert result.kicks_unresolved == 1
        assert result.kicks_failed == 1
        assert result.error_messages == [f"kick_id={failed_kick_id} lookup failed for 0xcccccccccccccccccccccccccccccccccccccccc"]

        rows = session.execute(
            select(models.kick_txs).order_by(models.kick_txs.c.id.asc())
        ).mappings().all()
        rows_by_id = {row["id"]: row for row in rows}
        assert rows_by_id[unresolved_kick_id]["auctionscan_round_id"] is None
        assert rows_by_id[unresolved_kick_id]["auctionscan_last_checked_at"] is not None
        assert rows_by_id[failed_kick_id]["auctionscan_round_id"] is None
        assert rows_by_id[failed_kick_id]["auctionscan_last_checked_at"] is None
