"""Read models for scan-run history."""

from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tidal.ops.logs import ScanRunRecord
from tidal.persistence import models


class ScanLogReadService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_runs(
        self,
        *,
        limit: int,
        offset: int = 0,
        status: str | None = None,
    ) -> dict[str, object]:
        count_stmt = select(func.count()).select_from(models.scan_runs)
        stmt = select(models.scan_runs)
        if status is not None:
            count_stmt = count_stmt.where(models.scan_runs.c.status == status)
            stmt = stmt.where(models.scan_runs.c.status == status)
        total = int(self.session.execute(count_stmt).scalar_one())
        stmt = stmt.order_by(models.scan_runs.c.started_at.desc()).limit(limit).offset(offset)
        rows = [dict(row) for row in self.session.execute(stmt).mappings().all()]
        if not rows:
            return {"items": [], "total": total}

        run_ids = [str(row["run_id"]) for row in rows]
        error_stmt = (
            select(models.scan_item_errors.c.run_id, func.count(models.scan_item_errors.c.id))
            .where(models.scan_item_errors.c.run_id.in_(run_ids))
            .group_by(models.scan_item_errors.c.run_id)
        )
        error_counts = {str(run_id): int(count) for run_id, count in self.session.execute(error_stmt).all()}
        items = [
            asdict(
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
            )
            for row in rows
        ]
        return {"items": items, "total": total}

