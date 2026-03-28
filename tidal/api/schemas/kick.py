"""Kick request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KickInspectRequest(BaseModel):
    source_type: str | None = Field(default=None, alias="sourceType")
    source_address: str | None = Field(default=None, alias="sourceAddress")
    auction_address: str | None = Field(default=None, alias="auctionAddress")
    limit: int | None = Field(default=None, ge=1)

    model_config = {"populate_by_name": True}


class KickPrepareRequest(KickInspectRequest):
    sender: str | None = None

