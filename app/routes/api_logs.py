from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.schemas import LogsResponse
from app.services.log_service import list_log_entries


router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


@router.get("", response_model=LogsResponse)
def get_logs_endpoint(
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
    level: Annotated[str | None, Query(max_length=20)] = None,
    logger: Annotated[str | None, Query(max_length=120)] = None,
    query: Annotated[str | None, Query(max_length=200)] = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> dict[str, Any]:
    return list_log_entries(
        limit=limit,
        level=level,
        logger_name=logger,
        query=query,
        order=order,
    )
