from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.schemas import StatsResponseModel

from app.services.stats_service import (
    build_stats,
    build_stats2_charts,
    parse_limit,
)


router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("", response_model=StatsResponseModel)
def get_stats(
    limit: Annotated[str | None, Query()] = "30",
) -> dict[str, Any]:
    parsed_limit = parse_limit(limit, default=30)
    stats = build_stats(limit=parsed_limit)
    charts = build_stats2_charts(stats)

    return {
        "limit": "all" if parsed_limit is None else parsed_limit,
        "stats": stats,
        "charts": charts,
    }
