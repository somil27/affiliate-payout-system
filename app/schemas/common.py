"""Shared pagination + error envelopes."""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageMeta(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str | None = None
