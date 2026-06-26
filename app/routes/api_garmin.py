import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    GarminDailyMetricsResponse,
    GarminDisconnectResponse,
    GarminLoginRequest,
    GarminLoginResponse,
    GarminMfaRequest,
    GarminStatsResponse,
    GarminStatusResponse,
    GarminSyncRequest,
    GarminSyncResponse,
)
from app.services.garmin_service import garmin_service


router = APIRouter(prefix="/api/v1/garmin", tags=["garmin"])


def garmin_error(exc: Exception) -> HTTPException:
    if isinstance(exc, sqlite3.IntegrityError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/status", response_model=GarminStatusResponse)
def get_garmin_status() -> dict[str, Any]:
    return garmin_service.status()


@router.post("/login", response_model=GarminLoginResponse)
def login_garmin(payload: GarminLoginRequest) -> dict[str, Any]:
    try:
        return garmin_service.login(payload.username, payload.password)
    except Exception as exc:
        raise garmin_error(exc) from exc


@router.post("/mfa", response_model=GarminLoginResponse)
def submit_garmin_mfa(payload: GarminMfaRequest) -> dict[str, Any]:
    try:
        return garmin_service.submit_mfa(payload.mfa_token, payload.code)
    except Exception as exc:
        raise garmin_error(exc) from exc


@router.post("/disconnect", response_model=GarminDisconnectResponse)
def disconnect_garmin() -> dict[str, Any]:
    try:
        return garmin_service.disconnect()
    except Exception as exc:
        raise garmin_error(exc) from exc


@router.post("/sync", response_model=GarminSyncResponse)
def sync_garmin(payload: GarminSyncRequest | None = None) -> dict[str, Any]:
    try:
        return garmin_service.sync(payload.days if payload else None)
    except Exception as exc:
        raise garmin_error(exc) from exc


@router.get("/daily", response_model=GarminDailyMetricsResponse)
def get_garmin_daily_metrics(
    days: int = Query(default=35, ge=1, le=90),
) -> dict[str, Any]:
    try:
        return garmin_service.list_daily(days)
    except Exception as exc:
        raise garmin_error(exc) from exc


@router.get("/stats", response_model=GarminStatsResponse)
def get_garmin_stats(
    range_value: str = Query(default="90", alias="range"),
) -> dict[str, Any]:
    try:
        return garmin_service.stats(range_value)
    except Exception as exc:
        raise garmin_error(exc) from exc
