"""Common API schemas."""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    status: Literal["ok", "noop", "error"]
    warnings: list[str] = Field(default_factory=list)
    data: T | dict | list | None = None


class PaginationParams(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)

