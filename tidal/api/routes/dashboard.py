"""Dashboard routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from tidal.api.auth import OperatorIdentity
from tidal.api.dependencies import get_operator, get_session
from tidal.api.services.dashboard import load_dashboard

router = APIRouter()


@router.get("/dashboard")
def get_dashboard(
    session: Session = Depends(get_session),
    _operator: OperatorIdentity = Depends(get_operator),
) -> dict[str, object]:
    return {"status": "ok", "warnings": [], "data": load_dashboard(session)}

