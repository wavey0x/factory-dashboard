"""Dashboard API service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from tidal.read.dashboard import DashboardReadService


def load_dashboard(session: Session) -> dict[str, object]:
    return DashboardReadService(session).load()

