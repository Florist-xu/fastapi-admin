from dataclasses import dataclass
from typing import Any, Dict

from fastapi import Query


@dataclass(frozen=True)
class PageParams:
    current: int
    size: int
    offset: int


def get_page_params(
    current: int = Query(1, ge=1, description="当前页码"),
    size: int = Query(10, ge=1, le=1000, description="每页数量"),
) -> PageParams:
    offset = (current - 1) * size
    return PageParams(current=current, size=size, offset=offset)


async def paginate(queryset, current: int, size: int) -> Dict[str, Any]:
    offset = (current - 1) * size
    records = await queryset.offset(offset).limit(size)
    total = await queryset.count()
    return {"records": records, "total": total, "current": current, "size": size}
