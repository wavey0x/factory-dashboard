"""Read-side services for CLI log inspection."""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tidal.persistence import models


def _extract_quote_request_url(raw_payload: str | None) -> str | None:
    if not raw_payload:
        return None
    try:
        payload = json.loads(str(raw_payload))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    request_url = payload.get("requestUrl")
    return str(request_url) if request_url else None


@dataclass(slots=True)
class KickLogRecord:
    id: int
    run_id: str
    created_at: str
    operation_type: str
    status: str
    source_type: str | None
    source_address: str | None
    auction_address: str
    token_address: str
    token_symbol: str | None
    want_symbol: str | None
    usd_value: str | None
    error_message: str | None
    tx_hash: str | None
    quote_url: str | None


@dataclass(slots=True)
class ScanRunRecord:
    run_id: str
    started_at: str
    finished_at: str | None
    status: str
    vaults_seen: int
    strategies_seen: int
    pairs_seen: int
    pairs_succeeded: int
    pairs_failed: int
    error_summary: str | None
    error_count: int


@dataclass(slots=True)
class ScanItemErrorRecord:
    id: int
    stage: str
    error_code: str
    error_message: str
    source_type: str | None
    source_address: str | None
    token_address: str | None
    created_at: str


@dataclass(slots=True)
class TxnRunDetail:
    kind: str
    run_id: str
    started_at: str
    finished_at: str | None
    status: str
    candidates_found: int
    kicks_attempted: int
    kicks_succeeded: int
    kicks_failed: int
    live: bool
    error_summary: str | None
    records: list[KickLogRecord]


@dataclass(slots=True)
class ScanRunDetail:
    kind: str
    run_id: str
    started_at: str
    finished_at: str | None
    status: str
    vaults_seen: int
    strategies_seen: int
    pairs_seen: int
    pairs_succeeded: int
    pairs_failed: int
    error_summary: str | None
    errors: list[ScanItemErrorRecord]


RunDetail = TxnRunDetail | ScanRunDetail


def _kick_log_record_from_row(row: dict[str, object]) -> KickLogRecord:
    return KickLogRecord(
        id=int(row["id"]),
        run_id=str(row["run_id"]),
        created_at=str(row["created_at"]),
        operation_type=str(row.get("operation_type") or "kick"),
        status=str(row["status"]),
        source_type=str(row["source_type"]) if row.get("source_type") is not None else None,
        source_address=str(row["source_address"]) if row.get("source_address") is not None else None,
        auction_address=str(row["auction_address"]),
        token_address=str(row["token_address"]),
        token_symbol=str(row["token_symbol"]) if row.get("token_symbol") is not None else None,
        want_symbol=str(row["want_symbol"]) if row.get("want_symbol") is not None else None,
        usd_value=str(row["usd_value"]) if row.get("usd_value") is not None else None,
        error_message=str(row["error_message"]) if row.get("error_message") is not None else None,
        tx_hash=str(row["tx_hash"]) if row.get("tx_hash") is not None else None,
        quote_url=_extract_quote_request_url(
            str(row["quote_response_json"]) if row.get("quote_response_json") is not None else None
        ),
    )


def list_kick_logs(
    session: Session,
    *,
    source_address: str | None = None,
    auction_address: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> list[KickLogRecord]:
    stmt = select(models.kick_txs)
    if source_address is not None:
        stmt = stmt.where(models.kick_txs.c.source_address == source_address)
    if auction_address is not None:
        stmt = stmt.where(models.kick_txs.c.auction_address == auction_address)
    if status is not None:
        stmt = stmt.where(models.kick_txs.c.status == status)
    stmt = stmt.order_by(models.kick_txs.c.created_at.desc(), models.kick_txs.c.id.desc()).limit(limit)
    return [_kick_log_record_from_row(dict(row)) for row in session.execute(stmt).mappings().all()]


def list_scan_runs(
    session: Session,
    *,
    status: str | None = None,
    limit: int = 20,
) -> list[ScanRunRecord]:
    stmt = select(models.scan_runs)
    if status is not None:
        stmt = stmt.where(models.scan_runs.c.status == status)
    stmt = stmt.order_by(models.scan_runs.c.started_at.desc()).limit(limit)
    rows = [dict(row) for row in session.execute(stmt).mappings().all()]
    if not rows:
        return []

    run_ids = [str(row["run_id"]) for row in rows]
    error_stmt = (
        select(models.scan_item_errors.c.run_id, func.count(models.scan_item_errors.c.id))
        .where(models.scan_item_errors.c.run_id.in_(run_ids))
        .group_by(models.scan_item_errors.c.run_id)
    )
    error_counts = {str(run_id): int(count) for run_id, count in session.execute(error_stmt).all()}

    return [
        ScanRunRecord(
            run_id=str(row["run_id"]),
            started_at=str(row["started_at"]),
            finished_at=str(row["finished_at"]) if row.get("finished_at") is not None else None,
            status=str(row["status"]),
            vaults_seen=int(row["vaults_seen"]),
            strategies_seen=int(row["strategies_seen"]),
            pairs_seen=int(row["pairs_seen"]),
            pairs_succeeded=int(row["pairs_succeeded"]),
            pairs_failed=int(row["pairs_failed"]),
            error_summary=str(row["error_summary"]) if row.get("error_summary") is not None else None,
            error_count=error_counts.get(str(row["run_id"]), 0),
        )
        for row in rows
    ]


def get_run_detail(session: Session, run_id: str) -> RunDetail | None:
    txn_row = session.execute(
        select(models.txn_runs).where(models.txn_runs.c.run_id == run_id)
    ).mappings().first()
    if txn_row is not None:
        kick_rows = session.execute(
            select(models.kick_txs)
            .where(models.kick_txs.c.run_id == run_id)
            .order_by(models.kick_txs.c.id.asc())
        ).mappings().all()
        return TxnRunDetail(
            kind="kick",
            run_id=str(txn_row["run_id"]),
            started_at=str(txn_row["started_at"]),
            finished_at=str(txn_row["finished_at"]) if txn_row.get("finished_at") is not None else None,
            status=str(txn_row["status"]),
            candidates_found=int(txn_row["candidates_found"]),
            kicks_attempted=int(txn_row["kicks_attempted"]),
            kicks_succeeded=int(txn_row["kicks_succeeded"]),
            kicks_failed=int(txn_row["kicks_failed"]),
            live=bool(txn_row["live"]),
            error_summary=str(txn_row["error_summary"]) if txn_row.get("error_summary") is not None else None,
            records=[_kick_log_record_from_row(dict(row)) for row in kick_rows],
        )

    scan_row = session.execute(
        select(models.scan_runs).where(models.scan_runs.c.run_id == run_id)
    ).mappings().first()
    if scan_row is None:
        return None

    error_rows = session.execute(
        select(models.scan_item_errors)
        .where(models.scan_item_errors.c.run_id == run_id)
        .order_by(models.scan_item_errors.c.id.asc())
    ).mappings().all()
    return ScanRunDetail(
        kind="scan",
        run_id=str(scan_row["run_id"]),
        started_at=str(scan_row["started_at"]),
        finished_at=str(scan_row["finished_at"]) if scan_row.get("finished_at") is not None else None,
        status=str(scan_row["status"]),
        vaults_seen=int(scan_row["vaults_seen"]),
        strategies_seen=int(scan_row["strategies_seen"]),
        pairs_seen=int(scan_row["pairs_seen"]),
        pairs_succeeded=int(scan_row["pairs_succeeded"]),
        pairs_failed=int(scan_row["pairs_failed"]),
        error_summary=str(scan_row["error_summary"]) if scan_row.get("error_summary") is not None else None,
        errors=[
            ScanItemErrorRecord(
                id=int(row["id"]),
                stage=str(row["stage"]),
                error_code=str(row["error_code"]),
                error_message=str(row["error_message"]),
                source_type=str(row["source_type"]) if row.get("source_type") is not None else None,
                source_address=str(row["source_address"]) if row.get("source_address") is not None else None,
                token_address=str(row["token_address"]) if row.get("token_address") is not None else None,
                created_at=str(row["created_at"]),
            )
            for row in error_rows
        ],
    )
