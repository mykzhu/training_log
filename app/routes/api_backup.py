import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException

from app.db import get_db
from app.schemas import BackupMutationResponse, BackupPayloadResponse
from app.services.backup_service import (
    build_backup_payload,
    get_table_counts,
    reset_database_data,
    restore_backup_payload,
)
from app.services.draft_service import clear_active_workout_draft


router = APIRouter(prefix="/api/v1/backup", tags=["backup"])


def get_backup_counts() -> dict[str, int]:
    with get_db() as conn:
        return get_table_counts(conn)


@router.get("", response_model=BackupPayloadResponse)
def get_backup() -> dict[str, Any]:
    return build_backup_payload()


@router.post("/import", response_model=BackupMutationResponse)
def import_backup_payload(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        restore_backup_payload(payload)
    except (ValueError, sqlite3.IntegrityError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    clear_active_workout_draft()

    return {
        "restored": True,
        "counts": get_backup_counts(),
    }


@router.post("/reset", response_model=BackupMutationResponse)
def reset_backup_data() -> dict[str, Any]:
    clear_active_workout_draft()
    reset_database_data()

    return {
        "reset": True,
        "counts": get_backup_counts(),
    }
