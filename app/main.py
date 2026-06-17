import logging
import time
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from app import config
from app.db import init_db
from app.routes.api_backup import router as backup_api_router
from app.routes.api_current_workout import router as current_workout_api_router
from app.routes.api_exercises import (
    profiles_router as exercise_profiles_api_router,
    router as exercises_api_router,
)
from app.routes.api_stats import router as stats_api_router
from app.routes.api_workouts import (
    router as workouts_api_router,
    workout_items_router as workout_items_api_router,
)


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.DEBUG),
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "[%(name)s] "
            "%(message)s"
        ),
    )


configure_logging()

logger = logging.getLogger("training_log")
access_logger = logging.getLogger("training_log.access")

app = FastAPI(title="Training Log")
app.include_router(backup_api_router)
app.include_router(current_workout_api_router)
app.include_router(exercises_api_router)
app.include_router(exercise_profiles_api_router)
app.include_router(stats_api_router)
app.include_router(workout_items_api_router)
app.include_router(workouts_api_router)


def get_frontend_dist_dir() -> Path:
    configured_dir = Path(config.FRONTEND_DIST_DIR)
    if (configured_dir / "index.html").is_file():
        return configured_dir

    local_vite_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    if (local_vite_dist / "index.html").is_file():
        return local_vite_dist

    return configured_dir


def get_frontend_file(path: str) -> Path | None:
    dist_dir = get_frontend_dist_dir().resolve()

    if not path:
        return dist_dir / "index.html"

    requested_path = (dist_dir / path).resolve()
    if dist_dir not in requested_path.parents:
        return None

    if requested_path.is_file():
        return requested_path

    if path.startswith("assets/"):
        return None

    return dist_dir / "index.html"


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("x-request-id", uuid4().hex[:8])
    start_time = time.perf_counter()

    client_host = request.client.host if request.client else "-"
    method = request.method
    path = request.url.path

    access_logger.info(
        "request.start request_id=%s method=%s path=%s client=%s",
        request_id,
        method,
        path,
        client_host,
    )

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start_time) * 1000
        access_logger.exception(
            "request.error request_id=%s method=%s path=%s client=%s duration_ms=%.2f",
            request_id,
            method,
            path,
            client_host,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start_time) * 1000
    access_logger.info(
        "request.end request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f",
        request_id,
        method,
        path,
        response.status_code,
        duration_ms,
    )

    response.headers["X-Request-ID"] = request_id
    return response


@app.on_event("startup")
def on_startup() -> None:
    logger.info(
        "app.startup db_path=%s log_level=%s frontend_dist=%s",
        config.DB_PATH,
        config.LOG_LEVEL,
        get_frontend_dist_dir(),
    )
    init_db()
    logger.info("app.ready")


@app.get("/{path:path}", include_in_schema=False)
def serve_react_app(path: str = "") -> FileResponse:
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found.")

    frontend_file = get_frontend_file(path)
    if frontend_file is None:
        raise HTTPException(status_code=404, detail="Not found.")

    if not frontend_file.is_file():
        raise HTTPException(
            status_code=503,
            detail="React frontend is not built. Run npm run build in frontend/.",
        )

    return FileResponse(frontend_file)
