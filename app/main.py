import json
import logging
import os
import sqlite3
import time
from datetime import datetime, date
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates


DB_PATH = Path(os.getenv("DB_PATH", "data/training.db"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
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
templates = Jinja2Templates(directory="app/templates")

BACKUP_SCHEMA_VERSION = 1
BACKUP_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "exercises": ("id", "name"),
    "workouts": (
        "id",
        "workout_date",
        "created_at",
        "finished_at",
        "session_rpe",
        "lower_back_pain",
    ),
    "workout_exercises": ("id", "workout_id", "exercise_id", "position"),
    "set_entries": (
        "id",
        "workout_exercise_id",
        "set_number",
        "weight",
        "reps",
        "created_at",
    ),
}
BACKUP_TABLES = tuple(BACKUP_TABLE_COLUMNS)

def format_datetime(value: str | None) -> str:
    if not value:
        return "—"

    return value.replace("T", " ")[:16]


def datetime_local_value(value: str | None) -> str:
    if not value:
        return ""

    return value[:16]


def parse_optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None

    return int(value)

def redirect_after_change(
    return_to: str | None = None,
    workout_id: int | None = None,
):
    if return_to == "edit_workout" and workout_id is not None:
        return RedirectResponse(f"/workouts/{workout_id}/edit", status_code=303)

    return RedirectResponse("/", status_code=303)

templates.env.filters["format_datetime"] = format_datetime
templates.env.filters["datetime_local_value"] = datetime_local_value


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


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {
        table_name: conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        for table_name in BACKUP_TABLES
    }
    logger.debug("db.table_counts counts=%s", counts)
    return counts


def build_backup_payload() -> dict[str, Any]:
    with get_db() as conn:
        tables = {}

        for table_name, columns in BACKUP_TABLE_COLUMNS.items():
            column_sql = ", ".join(columns)
            rows = conn.execute(
                f"SELECT {column_sql} FROM {table_name} ORDER BY id ASC"
            ).fetchall()
            tables[table_name] = [dict(row) for row in rows]

    payload = {
        "app": "training-log",
        "schema_version": BACKUP_SCHEMA_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "tables": tables,
    }
    logger.info(
        "backup.build schema_version=%s counts=%s",
        BACKUP_SCHEMA_VERSION,
        {table_name: len(rows) for table_name, rows in tables.items()},
    )
    return payload


def validate_backup_payload(payload: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(payload, dict):
        raise ValueError("Backup file must contain a JSON object.")

    if payload.get("schema_version") != BACKUP_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported backup schema version. Expected {BACKUP_SCHEMA_VERSION}."
        )

    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("Backup file is missing the tables object.")

    validated: dict[str, list[dict[str, Any]]] = {}

    for table_name, columns in BACKUP_TABLE_COLUMNS.items():
        rows = tables.get(table_name)
        if not isinstance(rows, list):
            raise ValueError(f"Backup table {table_name} must be a list.")

        validated_rows: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise ValueError(f"Row {index} in {table_name} must be an object.")

            missing_columns = [column for column in columns if column not in row]
            if missing_columns:
                missing = ", ".join(missing_columns)
                raise ValueError(f"Row {index} in {table_name} is missing {missing}.")

            validated_rows.append({column: row[column] for column in columns})

        validated[table_name] = validated_rows

    logger.info(
        "backup.validate.success schema_version=%s counts=%s",
        BACKUP_SCHEMA_VERSION,
        {table_name: len(rows) for table_name, rows in validated.items()},
    )
    return validated


def reset_sqlite_sequences(conn: sqlite3.Connection) -> None:
    logger.debug("db.sqlite_sequence.reset.start")
    placeholders = ", ".join("?" for _ in BACKUP_TABLES)
    conn.execute(
        f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})",
        BACKUP_TABLES,
    )

    for table_name in BACKUP_TABLES:
        max_id = conn.execute(
            f"SELECT COALESCE(MAX(id), 0) FROM {table_name}"
        ).fetchone()[0]

        if max_id:
            conn.execute(
                "INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)",
                (table_name, max_id),
            )

    logger.debug("db.sqlite_sequence.reset.done")


def restore_backup_payload(payload: Any) -> None:
    tables = validate_backup_payload(payload)
    logger.warning(
        "backup.restore.start counts=%s",
        {table_name: len(rows) for table_name, rows in tables.items()},
    )

    with get_db() as conn:
        for table_name in reversed(BACKUP_TABLES):
            conn.execute(f"DELETE FROM {table_name}")

        for table_name, columns in BACKUP_TABLE_COLUMNS.items():
            column_sql = ", ".join(columns)
            placeholders = ", ".join("?" for _ in columns)
            insert_sql = (
                f"INSERT INTO {table_name} ({column_sql}) "
                f"VALUES ({placeholders})"
            )

            for row in tables[table_name]:
                conn.execute(insert_sql, tuple(row[column] for column in columns))

        reset_sqlite_sequences(conn)

    logger.warning(
        "backup.restore.done counts=%s",
        {table_name: len(rows) for table_name, rows in tables.items()},
    )

def ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }

    if column_name not in columns:
        logger.info(
            "db.migration.add_column table=%s column=%s definition=%s",
            table_name,
            column_name,
            column_definition,
        )
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )

def init_db() -> None:
    logger.info("db.init.start db_path=%s", DB_PATH)

    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workout_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                finished_at TEXT
            );

            CREATE TABLE IF NOT EXISTS workout_exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workout_id INTEGER NOT NULL,
                exercise_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                FOREIGN KEY (workout_id) REFERENCES workouts(id) ON DELETE CASCADE,
                FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS set_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workout_exercise_id INTEGER NOT NULL,
                set_number INTEGER NOT NULL,
                weight REAL NOT NULL DEFAULT 0,
                reps INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (workout_exercise_id) REFERENCES workout_exercises(id) ON DELETE CASCADE
            );
            """
        )

        ensure_column(conn, "workouts", "session_rpe", "INTEGER")
        ensure_column(conn, "workouts", "lower_back_pain", "INTEGER")

        default_exercises = [
            "Deadlift",
            "Goblet Squat",
            "DB Bench Press",
            "DB Row",
            "EZ Curl",
            "Triceps Extension",
            "Lateral Raise",
            "Crunches",
        ]

        for exercise in default_exercises:
            conn.execute(
                "INSERT OR IGNORE INTO exercises (name) VALUES (?)",
                (exercise,),
            )

        logger.info("db.init.done")


@app.on_event("startup")
def on_startup() -> None:
    logger.info("app.startup db_path=%s log_level=%s", DB_PATH, LOG_LEVEL)
    init_db()
    logger.info("app.ready")


def get_or_create_active_workout() -> sqlite3.Row:
    with get_db() as conn:
        workout = conn.execute(
            """
            SELECT *
            FROM workouts
            WHERE finished_at IS NULL
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        if workout:
            logger.debug("workout.active.found workout_id=%s", workout["id"])
            return workout

        now = datetime.now().isoformat(timespec="seconds")

        cursor = conn.execute(
            """
            INSERT INTO workouts (workout_date, created_at)
            VALUES (?, ?)
            """,
            (date.today().isoformat(), now),
        )

        workout_id = cursor.lastrowid
        logger.info("workout.active.create workout_id=%s created_at=%s", workout_id, now)

        return conn.execute(
            "SELECT * FROM workouts WHERE id = ?",
            (workout_id,),
        ).fetchone()

def get_previous_set_for_exercise(
    exercise_id: int,
    current_workout_id: int,
) -> sqlite3.Row | None:
    with get_db() as conn:
        return conn.execute(
            """
            SELECT se.weight, se.reps
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
            JOIN workouts w ON w.id = we.workout_id
            WHERE we.exercise_id = ?
              AND w.id != ?
            ORDER BY w.workout_date DESC, w.id DESC, se.set_number DESC, se.id DESC
            LIMIT 1
            """,
            (exercise_id, current_workout_id),
        ).fetchone()

def get_workout_details(workout_id: int) -> list[dict[str, Any]]:
    with get_db() as conn:
        exercise_rows = conn.execute(
            """
            SELECT
                we.id AS workout_exercise_id,
                we.position,
                e.id AS exercise_id,
                e.name AS exercise_name
            FROM workout_exercises we
            JOIN exercises e ON e.id = we.exercise_id
            WHERE we.workout_id = ?
            ORDER BY we.position ASC, we.id ASC
            """,
            (workout_id,),
        ).fetchall()

        result: list[dict[str, Any]] = []

        for row in exercise_rows:
            sets = conn.execute(
                """
                SELECT *
                FROM set_entries
                WHERE workout_exercise_id = ?
                ORDER BY set_number ASC, id ASC
                """,
                (row["workout_exercise_id"],),
            ).fetchall()

            total_volume = sum(float(s["weight"]) * int(s["reps"]) for s in sets)
            total_reps = sum(int(s["reps"]) for s in sets)

            if sets:
                last_set = sets[-1]
                default_weight = float(last_set["weight"])
                default_reps = int(last_set["reps"])
            else:
                previous_set = get_previous_set_for_exercise(
                    exercise_id=row["exercise_id"],
                    current_workout_id=workout_id,
                )

                if previous_set:
                    default_weight = float(previous_set["weight"])
                    default_reps = int(previous_set["reps"])
                else:
                    default_weight = 0.0
                    default_reps = 10

            result.append(
                {
                    "workout_exercise_id": row["workout_exercise_id"],
                    "exercise_id": row["exercise_id"],
                    "exercise_name": row["exercise_name"],
                    "position": row["position"],
                    "sets": sets,
                    "total_volume": total_volume,
                    "total_reps": total_reps,
                    "default_weight": default_weight,
                    "default_reps": default_reps,
                }
            )

        return result


def get_weight_options(extra_weights: list[float] | None = None) -> list[float]:
    options: set[float] = set()

    # 0–70 kg, step 1 kg
    value = 0
    while value <= 70:
        options.add(float(value))
        value += 1

    # 75–150 kg, step 5 kg
    value = 75
    while value <= 150:
        options.add(float(value))
        value += 5

    if extra_weights:
        for weight in extra_weights:
            options.add(round(float(weight), 2))

    return sorted(options)

def renumber_sets(conn: sqlite3.Connection, workout_exercise_id: int) -> None:
    sets = conn.execute(
        """
        SELECT id
        FROM set_entries
        WHERE workout_exercise_id = ?
        ORDER BY set_number ASC, id ASC
        """,
        (workout_exercise_id,),
    ).fetchall()

    for index, set_row in enumerate(sets, start=1):
        conn.execute(
            """
            UPDATE set_entries
            SET set_number = ?
            WHERE id = ?
            """,
            (index, set_row["id"]),
        )

@app.get("/")
def index(request: Request):
    workout = get_or_create_active_workout()

    with get_db() as conn:
        exercises = conn.execute(
            "SELECT * FROM exercises ORDER BY name ASC"
        ).fetchall()

    workout_exercises = get_workout_details(workout["id"])

    total_volume = sum(item["total_volume"] for item in workout_exercises)
    total_reps = sum(item["total_reps"] for item in workout_exercises)
    total_sets = sum(len(item["sets"]) for item in workout_exercises)

    existing_weights: list[float] = []
    for item in workout_exercises:
        existing_weights.append(float(item["default_weight"]))
        for set_row in item["sets"]:
            existing_weights.append(float(set_row["weight"]))

    logger.debug(
        "page.index workout_id=%s exercises=%s sets=%s",
        workout["id"],
        len(workout_exercises),
        total_sets,
    )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "workout": workout,
            "exercises": exercises,
            "workout_exercises": workout_exercises,
            "reps_options": range(1, 51),
            "weight_options": get_weight_options(extra_weights=existing_weights),
            "total_volume": total_volume,
            "total_reps": total_reps,
            "total_sets": total_sets,
        },
    )


@app.post("/exercises")
def add_exercise(name: str = Form(...)):
    clean_name = name.strip()

    if clean_name:
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO exercises (name) VALUES (?)",
                (clean_name,),
            )
        logger.info("exercise.ensure name=%s", clean_name)
    else:
        logger.warning("exercise.create.skipped reason=empty_name")

    return RedirectResponse("/", status_code=303)


@app.post("/workouts/{workout_id}/exercise")
def add_exercise_to_workout(
    workout_id: int,
    exercise_id: int = Form(...),
    return_to: str | None = Form(None),
):
    with get_db() as conn:
        next_position = conn.execute(
            """
            SELECT COALESCE(MAX(position), 0) + 1
            FROM workout_exercises
            WHERE workout_id = ?
            """,
            (workout_id,),
        ).fetchone()[0]

        cursor = conn.execute(
            """
            INSERT INTO workout_exercises (workout_id, exercise_id, position)
            VALUES (?, ?, ?)
            """,
            (workout_id, exercise_id, next_position),
        )

        logger.info(
            "workout.exercise.add workout_id=%s workout_exercise_id=%s exercise_id=%s position=%s return_to=%s",
            workout_id,
            cursor.lastrowid,
            exercise_id,
            next_position,
            return_to,
        )

    return redirect_after_change(return_to, workout_id)


@app.post("/workout-exercises/{workout_exercise_id}/sets")
def add_set(
    workout_exercise_id: int,
    weight: float = Form(...),
    reps: int = Form(...),
    return_to: str | None = Form(None),
):
    with get_db() as conn:
        workout_exercise = conn.execute(
            """
            SELECT workout_id
            FROM workout_exercises
            WHERE id = ?
            """,
            (workout_exercise_id,),
        ).fetchone()

        if not workout_exercise:
            logger.warning(
                "set.add.not_found workout_exercise_id=%s return_to=%s",
                workout_exercise_id,
                return_to,
            )
            return RedirectResponse("/", status_code=303)

        workout_id = int(workout_exercise["workout_id"])

        next_set_number = conn.execute(
            """
            SELECT COALESCE(MAX(set_number), 0) + 1
            FROM set_entries
            WHERE workout_exercise_id = ?
            """,
            (workout_exercise_id,),
        ).fetchone()[0]

        cursor = conn.execute(
            """
            INSERT INTO set_entries
                (workout_exercise_id, set_number, weight, reps, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                workout_exercise_id,
                next_set_number,
                weight,
                reps,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

        logger.info(
            "set.add set_id=%s workout_id=%s workout_exercise_id=%s set_number=%s weight=%s reps=%s return_to=%s",
            cursor.lastrowid,
            workout_id,
            workout_exercise_id,
            next_set_number,
            weight,
            reps,
            return_to,
        )

    return redirect_after_change(return_to, workout_id)


@app.post("/sets/{set_id}/delete")
def delete_set(
    set_id: int,
    return_to: str | None = Form(None),
):
    workout_id: int | None = None

    with get_db() as conn:
        set_row = conn.execute(
            """
            SELECT
                se.workout_exercise_id,
                we.workout_id
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
            WHERE se.id = ?
            """,
            (set_id,),
        ).fetchone()

        if set_row:
            workout_exercise_id = int(set_row["workout_exercise_id"])
            workout_id = int(set_row["workout_id"])

            conn.execute(
                """
                DELETE FROM set_entries
                WHERE id = ?
                """,
                (set_id,),
            )

            renumber_sets(conn, workout_exercise_id)
            logger.info(
                "set.delete set_id=%s workout_id=%s workout_exercise_id=%s return_to=%s",
                set_id,
                workout_id,
                workout_exercise_id,
                return_to,
            )
        else:
            logger.warning("set.delete.not_found set_id=%s return_to=%s", set_id, return_to)

    return redirect_after_change(return_to, workout_id)


@app.post("/workout-exercises/{workout_exercise_id}/delete")
def delete_workout_exercise(
    workout_exercise_id: int,
    return_to: str | None = Form(None),
):
    workout_id: int | None = None

    with get_db() as conn:
        workout_exercise = conn.execute(
            """
            SELECT workout_id
            FROM workout_exercises
            WHERE id = ?
            """,
            (workout_exercise_id,),
        ).fetchone()

        if workout_exercise:
            workout_id = int(workout_exercise["workout_id"])

            conn.execute(
                """
                DELETE FROM workout_exercises
                WHERE id = ?
                """,
                (workout_exercise_id,),
            )
            logger.info(
                "workout.exercise.delete workout_exercise_id=%s workout_id=%s return_to=%s",
                workout_exercise_id,
                workout_id,
                return_to,
            )
        else:
            logger.warning(
                "workout.exercise.delete.not_found workout_exercise_id=%s return_to=%s",
                workout_exercise_id,
                return_to,
            )

    return redirect_after_change(return_to, workout_id)


@app.post("/workouts/{workout_id}/finish")
def finish_workout(workout_id: int):
    finished_at = datetime.now().isoformat(timespec="seconds")

    with get_db() as conn:
        conn.execute(
            """
            UPDATE workouts
            SET finished_at = ?
            WHERE id = ?
            """,
            (finished_at, workout_id),
        )

    logger.info("workout.finish workout_id=%s finished_at=%s", workout_id, finished_at)
    return RedirectResponse("/history", status_code=303)


@app.post("/workouts/new")
def new_workout():
    now = datetime.now().isoformat(timespec="seconds")

    with get_db() as conn:
        conn.execute(
            """
            UPDATE workouts
            SET finished_at = COALESCE(finished_at, ?)
            WHERE finished_at IS NULL
            """,
            (now,),
        )

        cursor = conn.execute(
            """
            INSERT INTO workouts (workout_date, created_at)
            VALUES (?, ?)
            """,
            (date.today().isoformat(), now),
        )

    logger.info("workout.new workout_id=%s created_at=%s", cursor.lastrowid, now)
    return RedirectResponse("/", status_code=303)


@app.get("/workouts/{workout_id}/edit")
def edit_workout_page(request: Request, workout_id: int):
    with get_db() as conn:
        workout = conn.execute(
            """
            SELECT *
            FROM workouts
            WHERE id = ?
            """,
            (workout_id,),
        ).fetchone()

        exercises = conn.execute(
            """
            SELECT *
            FROM exercises
            ORDER BY name ASC
            """
        ).fetchall()

    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    workout_exercises = get_workout_details(workout_id)

    total_volume = sum(item["total_volume"] for item in workout_exercises)
    total_reps = sum(item["total_reps"] for item in workout_exercises)
    total_sets = sum(len(item["sets"]) for item in workout_exercises)

    existing_weights: list[float] = []
    for item in workout_exercises:
        for set_row in item["sets"]:
            existing_weights.append(float(set_row["weight"]))

    logger.debug(
        "page.workout_edit workout_id=%s exercises=%s sets=%s",
        workout_id,
        len(workout_exercises),
        total_sets,
    )

    return templates.TemplateResponse(
        "edit_workout.html",
        {
            "request": request,
            "workout": workout,
            "exercises": exercises,
            "workout_exercises": workout_exercises,
            "reps_options": range(1, 51),
            "weight_options": get_weight_options(extra_weights=existing_weights),
            "total_volume": total_volume,
            "total_reps": total_reps,
            "total_sets": total_sets,
        },
    )


@app.post("/workouts/{workout_id}/update")
def update_workout(
    workout_id: int,
    created_at: str = Form(...),
    session_rpe: str | None = Form(None),
    lower_back_pain: str | None = Form(None),
):
    created_at = created_at.strip()

    # datetime-local sends YYYY-MM-DDTHH:MM
    if len(created_at) == 16:
        created_at = f"{created_at}:00"

    workout_date = created_at[:10]

    with get_db() as conn:
        parsed_session_rpe = parse_optional_int(session_rpe)
        parsed_lower_back_pain = parse_optional_int(lower_back_pain)

        conn.execute(
            """
            UPDATE workouts
            SET created_at = ?,
                workout_date = ?,
                session_rpe = ?,
                lower_back_pain = ?
            WHERE id = ?
            """,
            (
                created_at,
                workout_date,
                parsed_session_rpe,
                parsed_lower_back_pain,
                workout_id,
            ),
        )

    logger.info(
        "workout.update workout_id=%s created_at=%s workout_date=%s session_rpe=%s lower_back_pain=%s",
        workout_id,
        created_at,
        workout_date,
        parsed_session_rpe,
        parsed_lower_back_pain,
    )
    return RedirectResponse(f"/workouts/{workout_id}/edit", status_code=303)


@app.post("/workouts/{workout_id}/delete")
def delete_workout(workout_id: int):
    with get_db() as conn:
        conn.execute(
            """
            DELETE FROM workouts
            WHERE id = ?
            """,
            (workout_id,),
        )

    logger.warning("workout.delete workout_id=%s", workout_id)
    return RedirectResponse("/history", status_code=303)


@app.get("/backup")
def backup_page(request: Request):
    with get_db() as conn:
        counts = get_table_counts(conn)

    logger.debug("page.backup counts=%s", counts)
    return templates.TemplateResponse(
        "backup.html",
        {
            "request": request,
            "counts": counts,
        },
    )


@app.get("/backup/export.json")
def export_backup():
    payload = build_backup_payload()
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    logger.info("backup.export filename_timestamp=%s size_bytes=%s", timestamp, len(content.encode("utf-8")))
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="training-log-backup-{timestamp}.json"'
            )
        },
    )


@app.post("/backup/import")
async def import_backup(backup_file: UploadFile = File(...)):
    raw_content = await backup_file.read()
    logger.warning(
        "backup.import.received filename=%s size_bytes=%s",
        backup_file.filename,
        len(raw_content),
    )

    try:
        payload = json.loads(raw_content.decode("utf-8-sig"))
        restore_backup_payload(payload)
    except UnicodeDecodeError as exc:
        logger.exception("backup.import.error reason=utf8_decode filename=%s", backup_file.filename)
        raise HTTPException(
            status_code=400,
            detail="Backup file must be UTF-8 JSON.",
        ) from exc
    except json.JSONDecodeError as exc:
        logger.exception("backup.import.error reason=json_decode filename=%s", backup_file.filename)
        raise HTTPException(
            status_code=400,
            detail="Backup file is not valid JSON.",
        ) from exc
    except (ValueError, sqlite3.IntegrityError) as exc:
        logger.exception("backup.import.error reason=validation_or_integrity filename=%s", backup_file.filename)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.warning("backup.import.success filename=%s", backup_file.filename)
    return RedirectResponse("/history?restored=1", status_code=303)


@app.get("/history")
def history(request: Request):
    with get_db() as conn:
        workouts = conn.execute(
            """
            SELECT *
            FROM workouts
            ORDER BY id DESC
            LIMIT 30
            """
        ).fetchall()

    enriched = []

    for workout in workouts:
        details = get_workout_details(workout["id"])
        enriched.append(
            {
                "workout": workout,
                "total_volume": sum(item["total_volume"] for item in details),
                "total_reps": sum(item["total_reps"] for item in details),
                "total_sets": sum(len(item["sets"]) for item in details),
                "exercises_count": len(details),
            }
        )

    logger.debug("page.history workouts=%s restored=%s", len(enriched), request.query_params.get("restored") == "1")

    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "items": enriched,
            "restored": request.query_params.get("restored") == "1",
        },
    )

@app.get("/workouts/{workout_id}")
def workout_detail(request: Request, workout_id: int):
    with get_db() as conn:
        workout = conn.execute(
            """
            SELECT *
            FROM workouts
            WHERE id = ?
            """,
            (workout_id,),
        ).fetchone()

    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    workout_exercises = get_workout_details(workout_id)

    total_volume = sum(item["total_volume"] for item in workout_exercises)
    total_reps = sum(item["total_reps"] for item in workout_exercises)
    total_sets = sum(len(item["sets"]) for item in workout_exercises)

    logger.debug(
        "page.workout_detail workout_id=%s exercises=%s sets=%s",
        workout_id,
        len(workout_exercises),
        total_sets,
    )

    return templates.TemplateResponse(
        "workout.html",
        {
            "request": request,
            "workout": workout,
            "workout_exercises": workout_exercises,
            "total_volume": total_volume,
            "total_reps": total_reps,
            "total_sets": total_sets,
        },
    )

@app.post("/workout-exercises/{workout_exercise_id}/sets/duplicate")
def duplicate_set(
    workout_exercise_id: int,
    return_to: str | None = Form(None),
):
    with get_db() as conn:
        workout_exercise = conn.execute(
            """
            SELECT workout_id, exercise_id
            FROM workout_exercises
            WHERE id = ?
            """,
            (workout_exercise_id,),
        ).fetchone()

        if not workout_exercise:
            logger.warning(
                "set.duplicate.not_found workout_exercise_id=%s return_to=%s",
                workout_exercise_id,
                return_to,
            )
            return RedirectResponse("/", status_code=303)

        workout_id = int(workout_exercise["workout_id"])

        source_set = conn.execute(
            """
            SELECT weight, reps
            FROM set_entries
            WHERE workout_exercise_id = ?
            ORDER BY set_number DESC, id DESC
            LIMIT 1
            """,
            (workout_exercise_id,),
        ).fetchone()

        if not source_set:
            source_set = conn.execute(
                """
                SELECT se.weight, se.reps
                FROM set_entries se
                JOIN workout_exercises we ON we.id = se.workout_exercise_id
                JOIN workouts w ON w.id = we.workout_id
                WHERE we.exercise_id = ?
                  AND w.id != ?
                ORDER BY w.workout_date DESC, w.id DESC, se.set_number DESC, se.id DESC
                LIMIT 1
                """,
                (
                    workout_exercise["exercise_id"],
                    workout_exercise["workout_id"],
                ),
            ).fetchone()

        if not source_set:
            logger.warning(
                "set.duplicate.no_source workout_id=%s workout_exercise_id=%s return_to=%s",
                workout_id,
                workout_exercise_id,
                return_to,
            )
            return redirect_after_change(return_to, workout_id)

        next_set_number = conn.execute(
            """
            SELECT COALESCE(MAX(set_number), 0) + 1
            FROM set_entries
            WHERE workout_exercise_id = ?
            """,
            (workout_exercise_id,),
        ).fetchone()[0]

        cursor = conn.execute(
            """
            INSERT INTO set_entries
                (workout_exercise_id, set_number, weight, reps, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                workout_exercise_id,
                next_set_number,
                float(source_set["weight"]),
                int(source_set["reps"]),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

        logger.info(
            "set.duplicate set_id=%s workout_id=%s workout_exercise_id=%s set_number=%s weight=%s reps=%s return_to=%s",
            cursor.lastrowid,
            workout_id,
            workout_exercise_id,
            next_set_number,
            float(source_set["weight"]),
            int(source_set["reps"]),
            return_to,
        )

    return redirect_after_change(return_to, workout_id)


@app.post("/workouts/{workout_id}/metadata")
def update_workout_metadata(
    workout_id: int,
    session_rpe: int | None = Form(None),
    lower_back_pain: int | None = Form(None),
):
    with get_db() as conn:
        conn.execute(
            """
            UPDATE workouts
            SET session_rpe = ?,
                lower_back_pain = ?
            WHERE id = ?
            """,
            (session_rpe, lower_back_pain, workout_id),
        )

    logger.info(
        "workout.metadata.update workout_id=%s session_rpe=%s lower_back_pain=%s",
        workout_id,
        session_rpe,
        lower_back_pain,
    )
    return RedirectResponse("/", status_code=303)


@app.get("/sets/{set_id}/edit")
def edit_set_page(request: Request, set_id: int):
    with get_db() as conn:
        set_row = conn.execute(
            """
            SELECT
                se.id,
                se.workout_exercise_id,
                se.set_number,
                se.weight,
                se.reps,
                we.workout_id,
                e.name AS exercise_name
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
            JOIN exercises e ON e.id = we.exercise_id
            WHERE se.id = ?
            """,
            (set_id,),
        ).fetchone()

    if not set_row:
        raise HTTPException(status_code=404, detail="Set not found")

    logger.debug("page.set_edit set_id=%s workout_id=%s", set_id, set_row["workout_id"])

    return templates.TemplateResponse(
        "edit_set.html",
        {
            "request": request,
            "set": set_row,
            "weight_options": get_weight_options(
                extra_weights=[float(set_row["weight"])]
            ),
            "reps_options": range(1, 51),
        },
    )


@app.post("/sets/{set_id}/update")
def update_set(
    set_id: int,
    weight: float = Form(...),
    reps: int = Form(...),
    return_to: str | None = Form(None),
):
    with get_db() as conn:
        set_row = conn.execute(
            """
            SELECT we.workout_id
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
            WHERE se.id = ?
            """,
            (set_id,),
        ).fetchone()

        if not set_row:
            logger.warning("set.update.not_found set_id=%s return_to=%s", set_id, return_to)
            return RedirectResponse("/", status_code=303)

        workout_id = int(set_row["workout_id"])

        conn.execute(
            """
            UPDATE set_entries
            SET weight = ?,
                reps = ?
            WHERE id = ?
            """,
            (weight, reps, set_id),
        )

    logger.info(
        "set.update set_id=%s workout_id=%s weight=%s reps=%s return_to=%s",
        set_id,
        workout_id,
        weight,
        reps,
        return_to,
    )
    return redirect_after_change(return_to, workout_id)