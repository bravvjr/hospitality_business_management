"""Offset pagination helpers for list endpoints."""
from typing import Annotated, Generic, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel, Field

T = TypeVar("T")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class PaginationParams(BaseModel):
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


def get_pagination(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginationParams:
    return PaginationParams(limit=limit, offset=offset)


Pagination = Annotated[PaginationParams, Depends(get_pagination)]


def page_from(
    items: list[T],
    *,
    total: int,
    pagination: PaginationParams,
) -> Page[T]:
    return Page(
        items=items,
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )
