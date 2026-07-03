"""Pagination query dependency."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Query

from constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


@dataclass(frozen=True)
class Pagination:
    """Validated pagination parameters for list endpoints."""

    limit: int
    offset: int


def get_pagination(
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagination:
    """Build validated pagination parameters from query params."""
    return Pagination(limit=limit, offset=offset)
