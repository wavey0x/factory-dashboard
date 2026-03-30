"""Auction prepare request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AuctionDeployPrepareRequest(BaseModel):
    want: str
    receiver: str
    sender: str | None = None
    factory: str | None = None
    governance: str | None = None
    starting_price: int = Field(alias="startingPrice", ge=0)
    salt: str | None = None

    model_config = {"populate_by_name": True}


class AuctionEnableTokensPrepareRequest(BaseModel):
    sender: str | None = None
    extra_tokens: list[str] = Field(default_factory=list, alias="extraTokens")

    model_config = {"populate_by_name": True}


class AuctionSettlePrepareRequest(BaseModel):
    sender: str | None = None
    token_address: str | None = Field(default=None, alias="tokenAddress")
    sweep: bool = False

    model_config = {"populate_by_name": True}
