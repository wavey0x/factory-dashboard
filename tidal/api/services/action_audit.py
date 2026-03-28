"""Persistence and reconciliation for prepared operator actions."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tidal.config import Settings
from tidal.persistence import models
from tidal.persistence.db import Database
from tidal.persistence.repositories import APIActionRepository
from tidal.runtime import build_web3_client
from tidal.time import utcnow_iso


def create_prepared_action(
    session: Session,
    *,
    operator_id: str,
    action_type: str,
    sender: str | None,
    request_payload: dict[str, Any],
    preview_payload: dict[str, Any],
    transactions: list[dict[str, Any]],
    resource_address: str | None = None,
    auction_address: str | None = None,
    source_address: str | None = None,
    token_address: str | None = None,
) -> str:
    now = utcnow_iso()
    action_id = str(uuid.uuid4())
    repo = APIActionRepository(session)
    repo.create(
        action_row={
            "action_id": action_id,
            "action_type": action_type,
            "status": "PREPARED",
            "operator_id": operator_id,
            "sender": sender,
            "resource_address": resource_address,
            "auction_address": auction_address,
            "source_address": source_address,
            "token_address": token_address,
            "request_json": json.dumps(request_payload),
            "preview_json": json.dumps(preview_payload),
            "created_at": now,
            "updated_at": now,
        },
        transaction_rows=[
            {
                "action_id": action_id,
                "tx_index": index,
                "operation": tx["operation"],
                "to_address": tx["to"],
                "data": tx["data"],
                "value": tx.get("value", "0x0"),
                "chain_id": tx["chainId"],
                "gas_estimate": tx.get("gasEstimate"),
                "gas_limit": tx.get("gasLimit"),
                "created_at": now,
                "updated_at": now,
            }
            for index, tx in enumerate(transactions)
        ],
    )
    return action_id


def list_actions(
    session: Session,
    *,
    limit: int,
    offset: int,
    operator_id: str | None = None,
    status: str | None = None,
    action_type: str | None = None,
) -> dict[str, object]:
    repo = APIActionRepository(session)
    count_stmt = select(func.count()).select_from(models.api_actions)
    if operator_id is not None:
        count_stmt = count_stmt.where(models.api_actions.c.operator_id == operator_id)
    if status is not None:
        count_stmt = count_stmt.where(models.api_actions.c.status == status)
    if action_type is not None:
        count_stmt = count_stmt.where(models.api_actions.c.action_type == action_type)
    total = int(session.execute(count_stmt).scalar_one())
    rows = repo.list_actions(
        limit=limit,
        offset=offset,
        operator_id=operator_id,
        status=status,
        action_type=action_type,
    )
    items = [_action_summary(row, repo.get_action_transactions(str(row["action_id"]))) for row in rows]
    return {"items": items, "total": total}


def get_action(session: Session, action_id: str) -> dict[str, object] | None:
    repo = APIActionRepository(session)
    row = repo.get_action(action_id)
    if row is None:
        return None
    transactions = repo.get_action_transactions(action_id)
    return _action_detail(row, transactions)


def record_broadcast(
    session: Session,
    action_id: str,
    *,
    tx_index: int,
    tx_hash: str,
    broadcast_at: str,
) -> dict[str, object]:
    repo = APIActionRepository(session)
    repo.update_transaction_broadcast(
        action_id,
        tx_index=tx_index,
        tx_hash=tx_hash,
        broadcast_at=broadcast_at,
    )
    repo.update_action_status(action_id, status="BROADCAST_REPORTED", updated_at=broadcast_at)
    row = repo.get_action(action_id)
    assert row is not None
    return _action_detail(row, repo.get_action_transactions(action_id))


def record_receipt(
    session: Session,
    action_id: str,
    *,
    tx_index: int,
    receipt_status: str,
    block_number: int | None,
    gas_used: int | None,
    gas_price_gwei: str | None,
    observed_at: str,
    error_message: str | None = None,
) -> dict[str, object]:
    repo = APIActionRepository(session)
    repo.update_transaction_receipt(
        action_id,
        tx_index=tx_index,
        receipt_status=receipt_status,
        block_number=block_number,
        gas_used=gas_used,
        gas_price_gwei=gas_price_gwei,
        observed_at=observed_at,
        error_message=error_message,
    )
    transactions = repo.get_action_transactions(action_id)
    repo.update_action_status(
        action_id,
        status=_calculate_action_status(transactions),
        updated_at=observed_at,
        error_message=error_message if receipt_status in {"FAILED", "REVERTED"} else None,
    )
    row = repo.get_action(action_id)
    assert row is not None
    return _action_detail(row, repo.get_action_transactions(action_id))


async def run_receipt_reconciler(settings: Settings, database: Database) -> None:
    if not settings.rpc_url:
        return
    web3_client = build_web3_client(settings)
    interval_seconds = max(settings.tidal_api_receipt_reconcile_interval_seconds, 5)
    threshold_seconds = max(settings.tidal_api_receipt_reconcile_threshold_seconds, 0)
    try:
        while True:
            cutoff = (datetime.now(timezone.utc) - timedelta(seconds=threshold_seconds)).isoformat()
            with database.session() as session:
                repo = APIActionRepository(session)
                pending_rows = repo.pending_receipt_transactions(older_than=cutoff)
                for row in pending_rows:
                    tx_hash = row.get("tx_hash")
                    if not tx_hash:
                        continue
                    try:
                        receipt = await web3_client.get_transaction_receipt(str(tx_hash), timeout_seconds=2)
                    except Exception:  # noqa: BLE001
                        continue
                    observed_at = utcnow_iso()
                    effective_gas_price = receipt.get("effectiveGasPrice")
                    gas_price_gwei = str(round(effective_gas_price / 1e9, 4)) if effective_gas_price else None
                    record_receipt(
                        session,
                        str(row["action_id"]),
                        tx_index=int(row["tx_index"]),
                        receipt_status="CONFIRMED" if receipt.get("status") == 1 else "REVERTED",
                        block_number=receipt.get("blockNumber"),
                        gas_used=receipt.get("gasUsed"),
                        gas_price_gwei=gas_price_gwei,
                        observed_at=observed_at,
                    )
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        return


def _calculate_action_status(transactions: list[dict[str, object]]) -> str:
    receipt_statuses = [row.get("receipt_status") for row in transactions]
    if any(status == "FAILED" for status in receipt_statuses):
        return "FAILED"
    if any(status == "REVERTED" for status in receipt_statuses):
        return "REVERTED"
    if transactions and all(status == "CONFIRMED" for status in receipt_statuses):
        return "CONFIRMED"
    if any(row.get("tx_hash") for row in transactions):
        return "BROADCAST_REPORTED"
    return "PREPARED"


def _action_summary(action_row: dict[str, object], transactions: list[dict[str, object]]) -> dict[str, object]:
    return {
        "actionId": action_row["action_id"],
        "actionType": action_row["action_type"],
        "status": action_row["status"],
        "operatorId": action_row["operator_id"],
        "sender": action_row["sender"],
        "auctionAddress": action_row["auction_address"],
        "sourceAddress": action_row["source_address"],
        "tokenAddress": action_row["token_address"],
        "createdAt": action_row["created_at"],
        "updatedAt": action_row["updated_at"],
        "transactionCount": len(transactions),
        "transactions": [_transaction_payload(row) for row in transactions],
    }


def _action_detail(action_row: dict[str, object], transactions: list[dict[str, object]]) -> dict[str, object]:
    return {
        **_action_summary(action_row, transactions),
        "resourceAddress": action_row["resource_address"],
        "request": _decode_json(action_row.get("request_json")),
        "preview": _decode_json(action_row.get("preview_json")),
        "errorMessage": action_row.get("error_message"),
    }


def _transaction_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": row["id"],
        "txIndex": row["tx_index"],
        "operation": row["operation"],
        "to": row["to_address"],
        "data": row["data"],
        "value": row["value"],
        "chainId": row["chain_id"],
        "gasEstimate": row["gas_estimate"],
        "gasLimit": row["gas_limit"],
        "txHash": row["tx_hash"],
        "broadcastAt": row["broadcast_at"],
        "receiptStatus": row["receipt_status"],
        "blockNumber": row["block_number"],
        "gasUsed": row["gas_used"],
        "gasPriceGwei": row["gas_price_gwei"],
        "errorMessage": row["error_message"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _decode_json(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}

