"""Read models for single scan/txn run detail."""

from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.orm import Session

from tidal.ops.logs import get_run_detail


class RunLogReadService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_detail(self, run_id: str) -> dict[str, object] | None:
        detail = get_run_detail(self.session, run_id)
        if detail is None:
            return None
        return asdict(detail)

