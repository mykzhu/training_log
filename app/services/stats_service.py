from datetime import date, timedelta
from collections.abc import Mapping
from statistics import median
from typing import Any

from app.db import get_db
from app.repositories.exercises import derive_set_metrics, normalize_measurement_settings
from app.repositories.workouts import get_workout_details_batch
from app.services.analysis_service import (
    calculate_workout_load_metrics as calculate_load_metrics,
    estimated_1rm,
    list_exercise_profiles,
    runtime_profiles_by_key,
)
from app.services.date_service import app_today
from app.services.garmin_insights import metric_completeness
from app.services.training_load_service import build_training_load_summary


def get_best_e1rm_by_exercise(
    workout_exercises: list[dict[str, Any]],
    current_workout_id: int | None = None,
    as_of_created_at: str | None = None,
    as_of_workout_id: int | None = None,
) -> dict[int, float]:
    exercise_ids = sorted(
        {
            int(item["exercise_id"])
            for item in workout_exercises
            if item.get("exercise_id") is not None
        }
    )

    if not exercise_ids:
        return {}

    placeholders = ", ".join("?" for _ in exercise_ids)
    params: list[Any] = list(exercise_ids)

    workout_filter = ""
    if as_of_workout_id is None and current_workout_id is not None:
        as_of_workout_id = current_workout_id

    if as_of_created_at is None and as_of_workout_id is not None:
        with get_db() as conn:
            workout = conn.execute(
                """
                SELECT created_at
                FROM workouts
                WHERE id = ?
                """,
                (as_of_workout_id,),
            ).fetchone()

        if workout is not None:
            as_of_created_at = str(workout["created_at"])

    if as_of_created_at is not None and as_of_workout_id is not None:
        workout_filter = """
              AND (
                    w.created_at < ?
                    OR (w.created_at = ? AND w.id < ?)
              )
        """
        params.extend([as_of_created_at, as_of_created_at, as_of_workout_id])
    elif as_of_created_at is not None:
        workout_filter = "AND w.created_at < ?"
        params.append(as_of_created_at)
    elif current_workout_id is not None:
        workout_filter = "AND w.id != ?"
        params.append(current_workout_id)

    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT
                we.exercise_id,
                COALESCE(we.measurement_type, e.measurement_type, 'weighted_reps') AS measurement_type,
                se.weight,
                se.reps
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
            JOIN exercises e ON e.id = we.exercise_id
            JOIN workouts w ON w.id = we.workout_id
            WHERE we.exercise_id IN ({placeholders})
              {workout_filter}
            """,
            params,
        ).fetchall()

    best_by_exercise: dict[int, float] = {}

    for row in rows:
        exercise_id = int(row["exercise_id"])
        weight = float(row["weight"])
        reps = int(row["reps"])
        e1rm = estimated_1rm(weight, reps, row["measurement_type"])

        if e1rm is None:
            continue

        if exercise_id not in best_by_exercise or e1rm > best_by_exercise[exercise_id]:
            best_by_exercise[exercise_id] = e1rm

    return best_by_exercise


def calculate_workout_load_metrics(
    workout_exercises: list[dict[str, Any]],
    session_rpe: int | float | None = None,
    current_workout_id: int | None = None,
    as_of_created_at: str | None = None,
    as_of_workout_id: int | None = None,
    best_e1rm_by_exercise: dict[int, float] | None = None,
    profiles_by_key: Mapping[str, Mapping[str, float | str]] | None = None,
) -> dict[str, Any]:
    if best_e1rm_by_exercise is not None:
        return calculate_load_metrics(
            workout_exercises=workout_exercises,
            session_rpe=session_rpe,
            best_e1rm_by_exercise=best_e1rm_by_exercise,
            profiles_by_key=profiles_by_key,
        )

    best_e1rm_by_exercise = get_best_e1rm_by_exercise(
        workout_exercises=workout_exercises,
        current_workout_id=current_workout_id,
        as_of_created_at=as_of_created_at,
        as_of_workout_id=as_of_workout_id,
    )

    return calculate_load_metrics(
        workout_exercises=workout_exercises,
        session_rpe=session_rpe,
        best_e1rm_by_exercise=best_e1rm_by_exercise,
        profiles_by_key=profiles_by_key,
    )


def workout_created_at(workout: Any) -> str:
    return str(workout["created_at"])


def workout_id(workout: Any) -> int:
    return int(workout["id"])


def workout_sort_key(workout: Any) -> tuple[str, int]:
    return (workout_created_at(workout), workout_id(workout))

def workout_week_start(created_at: str) -> str:
    workout_day = date.fromisoformat(created_at[:10])
    monday = workout_day - timedelta(days=workout_day.weekday())
    return monday.isoformat()

def build_selected_week_starts(
    workouts: list[Any],
) -> list[str]:
    if not workouts:
        return []

    first_day = date.fromisoformat(
        workout_created_at(workouts[0])[:10]
    )
    last_day = date.fromisoformat(
        workout_created_at(workouts[-1])[:10]
    )

    current = first_day - timedelta(days=first_day.weekday())
    final = last_day - timedelta(days=last_day.weekday())

    weeks: list[str] = []

    while current <= final:
        weeks.append(current.isoformat())
        current += timedelta(days=7)

    return weeks

def row_is_before_workout(row: Any, workout: Any) -> bool:
    row_created_at = str(row["created_at"])
    target_created_at = workout_created_at(workout)
    row_workout_id = int(row["workout_id"])
    target_workout_id = workout_id(workout)

    return row_created_at < target_created_at or (
        row_created_at == target_created_at
        and row_workout_id < target_workout_id
    )


def build_e1rm_baselines_by_workout(
    workouts: list[Any],
    details_by_workout: dict[int, list[dict[str, Any]]],
) -> dict[int, dict[int, float]]:
    ordered_workouts = sorted(workouts, key=workout_sort_key)
    baselines_by_workout: dict[int, dict[int, float]] = {
        workout_id(workout): {}
        for workout in ordered_workouts
    }

    exercise_ids = sorted(
        {
            int(item["exercise_id"])
            for details in details_by_workout.values()
            for item in details
            if item.get("exercise_id") is not None
        }
    )
    if not ordered_workouts or not exercise_ids:
        return baselines_by_workout

    max_workout = ordered_workouts[-1]
    placeholders = ", ".join("?" for _ in exercise_ids)
    params: list[Any] = [
        *exercise_ids,
        workout_created_at(max_workout),
        workout_created_at(max_workout),
        workout_id(max_workout),
    ]

    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT
                we.exercise_id,
                w.id AS workout_id,
                w.created_at,
                COALESCE(we.measurement_type, e.measurement_type, 'weighted_reps') AS measurement_type,
                se.weight,
                se.reps
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
            JOIN exercises e ON e.id = we.exercise_id
            JOIN workouts w ON w.id = we.workout_id
            WHERE we.exercise_id IN ({placeholders})
              AND (
                    w.created_at < ?
                    OR (w.created_at = ? AND w.id < ?)
              )
            ORDER BY w.created_at ASC, w.id ASC, se.set_number ASC, se.id ASC
            """,
            params,
        ).fetchall()

    best_by_exercise: dict[int, float] = {}
    row_index = 0

    for workout in ordered_workouts:
        while row_index < len(rows) and row_is_before_workout(
            rows[row_index],
            workout,
        ):
            row = rows[row_index]
            exercise_id = int(row["exercise_id"])
            e1rm = estimated_1rm(
                float(row["weight"]),
                int(row["reps"]),
                row["measurement_type"],
            )
            if e1rm is not None:
                if exercise_id not in best_by_exercise or e1rm > best_by_exercise[exercise_id]:
                    best_by_exercise[exercise_id] = e1rm

            row_index += 1

        baselines_by_workout[workout_id(workout)] = dict(best_by_exercise)

    return baselines_by_workout

def build_weight_baselines_by_workout(
    workouts: list[Any],
    details_by_workout: dict[int, list[dict[str, Any]]],
) -> dict[int, dict[int, dict[int, float]]]:
    ordered_workouts = sorted(workouts, key=workout_sort_key)

    baselines_by_workout: dict[
        int,
        dict[int, dict[int, float]],
    ] = {
        workout_id(workout): {}
        for workout in ordered_workouts
    }

    exercise_ids = sorted(
        {
            int(item["exercise_id"])
            for details in details_by_workout.values()
            for item in details
            if item.get("exercise_id") is not None
        }
    )

    if not ordered_workouts or not exercise_ids:
        return baselines_by_workout

    max_workout = ordered_workouts[-1]
    placeholders = ", ".join("?" for _ in exercise_ids)

    params: list[Any] = [
        *exercise_ids,
        workout_created_at(max_workout),
        workout_created_at(max_workout),
        workout_id(max_workout),
    ]

    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT
                we.exercise_id,
                w.id AS workout_id,
                w.created_at,
                se.weight,
                se.reps
            FROM set_entries se
            JOIN workout_exercises we
              ON we.id = se.workout_exercise_id
            JOIN workouts w
              ON w.id = we.workout_id
            WHERE we.exercise_id IN ({placeholders})
              AND se.weight > 0
              AND se.reps > 0
              AND (
                    w.created_at < ?
                    OR (w.created_at = ? AND w.id < ?)
              )
            ORDER BY
                w.created_at ASC,
                w.id ASC,
                se.set_number ASC,
                se.id ASC
            """,
            params,
        ).fetchall()

    best_by_exercise: dict[int, dict[int, float]] = {}
    row_index = 0

    for workout in ordered_workouts:
        while row_index < len(rows) and row_is_before_workout(
            rows[row_index],
            workout,
        ):
            row = rows[row_index]

            exercise_id = int(row["exercise_id"])
            reps = int(row["reps"])
            weight = float(row["weight"])

            exercise_best = best_by_exercise.setdefault(
                exercise_id,
                {},
            )

            previous_best = exercise_best.get(reps)

            if previous_best is None or weight > previous_best:
                exercise_best[reps] = weight

            row_index += 1

        baselines_by_workout[workout_id(workout)] = {
            exercise_id: dict(reps_to_weight)
            for exercise_id, reps_to_weight
            in best_by_exercise.items()
        }

    return baselines_by_workout

def build_workout_analysis(
    workout_id: int,
    workout_exercises: list[dict[str, Any]],
) -> dict[str, Any]:
    exercise_analyses: list[dict[str, Any]] = []
    all_prs: list[dict[str, Any]] = []

    with get_db() as conn:
        current_workout = conn.execute(
            """
            SELECT id, created_at
            FROM workouts
            WHERE id = ?
            """,
            (workout_id,),
        ).fetchone()

        if not current_workout:
            return {
                "exercises": [],
                "prs": [],
            }

        current_created_at = current_workout["created_at"]

        for item in workout_exercises:
            exercise_id = int(item["exercise_id"])
            exercise_name = str(item["exercise_name"])
            measurement_type = str(item.get("measurement_type") or "weighted_reps")
            sets = item["sets"]

            current_max_weight: float | None = None
            current_max_reps: int | None = None
            current_best_e1rm: float | None = None
            current_best_e1rm_set: dict[str, Any] | None = None
            current_best_set: dict[str, Any] | None = None
            current_best_set_score = -1.0
            current_total_volume = float(item["total_volume"])

            for set_row in sets:
                weight = float(set_row["weight"])
                reps = int(set_row["reps"])
                volume = weight * reps

                if current_max_weight is None or weight > current_max_weight:
                    current_max_weight = weight

                if current_max_reps is None or reps > current_max_reps:
                    current_max_reps = reps

                e1rm = estimated_1rm(weight, reps, measurement_type)
                if e1rm is not None:
                    if current_best_e1rm is None or e1rm > current_best_e1rm:
                        current_best_e1rm = e1rm
                        current_best_e1rm_set = {
                            "weight": weight,
                            "reps": reps,
                        }

                if e1rm is not None:
                    score = e1rm
                elif weight > 0:
                    score = volume
                else:
                    score = reps

                if score > current_best_set_score:
                    current_best_set_score = score
                    current_best_set = {
                        "weight": weight,
                        "reps": reps,
                    }

            previous_rows = conn.execute(
                """
                SELECT
                    w.id AS workout_id,
                    w.created_at,
                    COALESCE(we.measurement_type, e.measurement_type, 'weighted_reps') AS measurement_type,
                    se.weight,
                    se.reps
                FROM set_entries se
                JOIN workout_exercises we ON we.id = se.workout_exercise_id
                JOIN exercises e ON e.id = we.exercise_id
                JOIN workouts w ON w.id = we.workout_id
                WHERE we.exercise_id = ?
                  AND (
                        w.created_at < ?
                        OR (w.created_at = ? AND w.id < ?)
                  )
                ORDER BY w.created_at ASC, w.id ASC, se.set_number ASC, se.id ASC
                """,
                (
                    exercise_id,
                    current_created_at,
                    current_created_at,
                    workout_id,
                ),
            ).fetchall()

            previous_max_weight: float | None = None
            previous_max_reps: int | None = None
            previous_best_e1rm: float | None = None

            for row in previous_rows:
                weight = float(row["weight"])
                reps = int(row["reps"])

                if previous_max_weight is None or weight > previous_max_weight:
                    previous_max_weight = weight

                if previous_max_reps is None or reps > previous_max_reps:
                    previous_max_reps = reps

                e1rm = estimated_1rm(weight, reps, row["measurement_type"])
                if e1rm is not None:
                    if previous_best_e1rm is None or e1rm > previous_best_e1rm:
                        previous_best_e1rm = e1rm

            previous_volume_rows = conn.execute(
                """
                SELECT
                    w.id AS workout_id,
                    SUM(se.weight * se.reps) AS exercise_volume
                FROM set_entries se
                JOIN workout_exercises we ON we.id = se.workout_exercise_id
                JOIN workouts w ON w.id = we.workout_id
                WHERE we.exercise_id = ?
                  AND (
                        w.created_at < ?
                        OR (w.created_at = ? AND w.id < ?)
                  )
                GROUP BY w.id
                """,
                (
                    exercise_id,
                    current_created_at,
                    current_created_at,
                    workout_id,
                ),
            ).fetchall()

            previous_best_volume: float | None = None
            for row in previous_volume_rows:
                volume = float(row["exercise_volume"] or 0)
                if previous_best_volume is None or volume > previous_best_volume:
                    previous_best_volume = volume

            pr_flags: list[str] = []

            if (
                current_max_weight is not None
                and current_max_weight > 0
                and previous_max_weight is not None
                and current_max_weight > previous_max_weight
            ):
                pr_flags.append("Weight PR")

            if (
                current_max_reps is not None
                and previous_max_reps is not None
                and current_max_reps > previous_max_reps
            ):
                pr_flags.append("Rep PR")

            if (
                current_best_e1rm is not None
                and previous_best_e1rm is not None
                and current_best_e1rm > previous_best_e1rm
            ):
                pr_flags.append("e1RM PR")

            if (
                current_total_volume > 0
                and previous_best_volume is not None
                and current_total_volume > previous_best_volume
            ):
                pr_flags.append("Volume PR")

            exercise_analysis = {
                "exercise_id": exercise_id,
                "exercise_name": exercise_name,
                "best_set": current_best_set,
                "best_e1rm": current_best_e1rm,
                "best_e1rm_set": current_best_e1rm_set,
                "pr_flags": pr_flags,
            }

            exercise_analyses.append(exercise_analysis)

            for flag in pr_flags:
                all_prs.append(
                    {
                        "exercise_name": exercise_name,
                        "type": flag,
                    }
                )

    return {
        "exercises": exercise_analyses,
        "prs": all_prs,
    }


# SPARK_CHARS = "_▁▂▃▄▅▆▇█"

SPARK_CHARS_INC = " ⢀⣀⣠⣤⣴⣶⣾⣿"
SPARK_CHARS_DEC = "⣿⣷⣶⣦⣤⣄⣀⡀ "


def build_sparkbar(
    values: list[float | int | None],
    width: int = 16,
    max_value: float | None = None,
) -> str:
    valid_values = [float(value) for value in values if value is not None]

    if not valid_values:
        return "—"

    values = list(values)

    if len(values) > width:
        bucketed_values: list[float | None] = []

        for index in range(width):
            start = int(index * len(values) / width)
            end = int((index + 1) * len(values) / width)

            bucket = [
                float(value)
                for value in values[start:end]
                if value is not None
            ]

            bucketed_values.append(
                sum(bucket) / len(bucket) if bucket else None
            )

        values = bucketed_values

    chart_max = max_value if max_value is not None else max(valid_values)

    if chart_max <= 0:
        return SPARK_CHARS_INC[0] * len(values)

    max_index = len(SPARK_CHARS_INC) - 1
    result: list[str] = []

    previous_value: float | None = None

    for value in values:
        if value is None:
            result.append("·")
            continue

        numeric_value = float(value)
        ratio = max(0.0, min(1.0, numeric_value / chart_max))
        level = round(ratio * max_index)

        if previous_value is not None and numeric_value < previous_value:
            # DEC is stored high→low, so invert level:
            # high value -> ⣿, low value -> space
            char = SPARK_CHARS_DEC[max_index - level]
        else:
            # INC is stored low→high:
            # low value -> space, high value -> ⣿
            char = SPARK_CHARS_INC[level]

        result.append(char)
        previous_value = numeric_value

    return "".join(result)


def build_calendar_heatmap(
    workouts: list[dict[str, Any]],
    value_key: str,
) -> dict[str, Any]:
    if not workouts:
        return {"weeks": []}

    daily: dict[date, dict[str, Any]] = {}

    for workout in workouts:
        workout_date = date.fromisoformat(workout["date"])

        if workout_date not in daily:
            daily[workout_date] = {
                "date": workout["date"],
                "count": 0,
                "value": None,
                "workout_id": workout["id"],
            }

        day = daily[workout_date]
        day["count"] += 1
        day["workout_id"] = workout["id"]

        value = workout.get(value_key)
        if value is not None:
            numeric_value = float(value)

            # If multiple workouts exist on one day, show the worst value.
            if day["value"] is None or numeric_value > day["value"]:
                day["value"] = numeric_value

    first_day = min(daily)
    last_day = max(daily)

    calendar_start = first_day - timedelta(days=first_day.weekday())
    calendar_end = last_day + timedelta(days=6 - last_day.weekday())

    weeks = []
    current = calendar_start

    while current <= calendar_end:
        week_days = []
        month_label = ""

        for offset in range(7):
            current_day = current + timedelta(days=offset)

            if current_day.day == 1 or current_day == calendar_start:
                month_label = current_day.strftime("%b")

            day_data = daily.get(current_day)

            if day_data:
                week_days.append(
                    {
                        "date": current_day.isoformat(),
                        "day": current_day.day,
                        "has_workout": True,
                        "count": day_data["count"],
                        "value": day_data["value"],
                        "workout_id": day_data["workout_id"],
                    }
                )
            else:
                week_days.append(
                    {
                        "date": current_day.isoformat(),
                        "day": current_day.day,
                        "has_workout": False,
                        "count": 0,
                        "value": None,
                        "workout_id": None,
                    }
                )

        weeks.append(
            {
                "month_label": month_label,
                "days": week_days,
            }
        )

        current += timedelta(days=7)

    return {"weeks": weeks}


def parse_limit(value: str | None, default: int = 30) -> int | None:
    if value == "all":
        return None

    if not value:
        return default

    try:
        parsed = int(value)
    except ValueError:
        return default

    return max(1, min(parsed, 500))


def build_line_chart_series(
    workouts: list[dict[str, Any]],
    value_key: str,
    max_value: float | None = None,
) -> dict[str, Any]:
    points: list[str] = []
    markers: list[dict[str, Any]] = []

    raw_values: list[float | None] = []
    for workout in workouts:
        value = workout.get(value_key)
        raw_values.append(float(value) if value is not None else None)

    valid_values = [value for value in raw_values if value is not None]

    if not valid_values:
        return {
            "points": "",
            "area_points": "",
            "markers": [],
            "max_value": None,
        }

    chart_max = max_value if max_value is not None else max(valid_values)
    if chart_max <= 0:
        chart_max = 1.0

    count = len(workouts)

    for index, workout in enumerate(workouts):
        value = raw_values[index]
        if value is None:
            continue

        x = 50.0 if count <= 1 else index / (count - 1) * 100
        y = 100 - min(100, max(0, value / chart_max * 100))

        points.append(f"{x:.2f},{y:.2f}")
        markers.append(
            {
                "x": x,
                "y": y,
                "value": value,
                "date": workout["date"],
                "workout_id": workout["id"],
            }
        )

    area_points = ""
    if markers:
        area_points = (
            f"{markers[0]['x']:.2f},100 "
            f"{' '.join(points)} "
            f"{markers[-1]['x']:.2f},100"
        )

    return {
        "points": " ".join(points),
        "area_points": area_points,
        "markers": markers,
        "max_value": chart_max,
    }


def build_scatter_points(workouts: list[dict[str, Any]]) -> dict[str, Any]:
    valid_items = [
        workout
        for workout in workouts
        if workout["load_score"] > 0
        and workout["lower_back_pain"] is not None
    ]

    if not valid_items:
        return {
            "points": [],
            "max_volume": None,
            "max_load": None,
        }

    max_load = max(float(item["load_score"]) for item in valid_items)
    if max_load <= 0:
        max_load = 1.0
    max_volume = max(float(item["total_volume"]) for item in valid_items)

    points = []

    for workout in valid_items:
        load = float(workout["load_score"])
        volume = float(workout["total_volume"])
        back = float(workout["lower_back_pain"])

        points.append(
            {
                "x": min(100, max(0, load / max_load * 100)),
                "y": 100 - min(100, max(0, back / 10 * 100)),
                "load": load,
                "volume": volume,
                "total_volume_kg": float(workout["total_volume_kg"]),
                "back": back,
                "date": workout["date"],
                "workout_id": workout["id"],
            }
        )

    return {
        "points": points,
        "max_volume": max_volume,
        "max_load": max_load,
    }


def data_quality_warning(
    *,
    key: str,
    severity: str,
    title: str,
    message: str,
    count: int | None = None,
    workout_id: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "key": key,
        "severity": severity,
        "title": title,
        "message": message,
    }
    if count is not None:
        payload["count"] = count
    if workout_id is not None:
        payload["workout_id"] = workout_id
    return payload


def latest_garmin_metric_from_workouts(workouts: list[Any]) -> dict[str, Any] | None:
    if not workouts:
        return None

    first = workouts[0]
    if first["latest_garmin_date"] is None:
        return None

    return {
        "date": first["latest_garmin_date"],
        "resting_heart_rate": first["latest_garmin_resting_heart_rate"],
        "hrv_ms": first["latest_garmin_hrv_ms"],
        "stress_avg": first["latest_garmin_stress_avg"],
        "body_battery_start": first["latest_garmin_body_battery_start"],
        "body_battery_end": first["latest_garmin_body_battery_end"],
        "steps": first["latest_garmin_steps"],
        "synced_at": first["latest_garmin_synced_at"],
    }


def build_data_quality_warnings(
    *,
    workouts: list[dict[str, Any]],
    summary: dict[str, Any],
    zero_kg_weighted_set_count: int,
    latest_garmin_metric: dict[str, Any] | None = None,
    today: date | None = None,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []

    if int(summary["bodyweight_reps"]) > 0:
        warnings.append(
            data_quality_warning(
                key="bodyweight_excluded_from_kg_volume",
                severity="info",
                title="Bodyweight work is separate from kg volume",
                message=(
                    "Some sessions contain bodyweight-only work. Kg volume excludes "
                    "this work; use load and back-stress charts for total dose."
                ),
                count=int(summary["bodyweight_reps"]),
            )
        )

    load_values = [
        float(workout["load_score"])
        for workout in workouts
        if float(workout["load_score"]) > 0
    ]
    load_median = median(load_values) if load_values else None
    high_pain_low_load = [
        workout
        for workout in workouts
        if workout["lower_back_pain"] is not None
        and int(workout["lower_back_pain"]) >= 6
        and load_median is not None
        and float(workout["load_score"]) < float(load_median)
    ]
    if high_pain_low_load:
        latest = high_pain_low_load[-1]
        warnings.append(
            data_quality_warning(
                key="high_pain_low_load",
                severity="watch",
                title="High pain on a lower-load session",
                message=(
                    "High lower-back pain was logged on a session below the recent "
                    "median load. This may reflect background pain rather than workout dose."
                ),
                count=len(high_pain_low_load),
                workout_id=int(latest["id"]),
            )
        )

    if workouts:
        rpe_logged = sum(1 for workout in workouts if workout["session_rpe"] is not None)
        pain_logged = sum(
            1 for workout in workouts if workout["lower_back_pain"] is not None
        )
        minimum_feedback_count = len(workouts) * 0.7
        if rpe_logged < minimum_feedback_count or pain_logged < minimum_feedback_count:
            warnings.append(
                data_quality_warning(
                    key="missing_feedback",
                    severity="info",
                    title="Feedback coverage is low",
                    message=(
                        "Add RPE and lower-back pain feedback to improve trend quality."
                    ),
                    count=len(workouts) - min(rpe_logged, pain_logged),
                )
            )

    if zero_kg_weighted_set_count > 0:
        warnings.append(
            data_quality_warning(
                key="zero_kg_weighted_sets",
                severity="info",
                title="Some weighted exercises include 0 kg sets",
                message=(
                    "If these are warmups or bodyweight sets, this is okay; they will "
                    "not add kg volume."
                ),
                count=zero_kg_weighted_set_count,
            )
        )

    today = today or app_today()
    latest_garmin_completeness = metric_completeness(
        latest_garmin_metric,
        today=today,
    )
    if (
        latest_garmin_metric is not None
        and not latest_garmin_completeness["is_complete"]
    ):
        status = str(latest_garmin_completeness["completeness_status"])
        if status in {"partial_today", "partial_sync"}:
            warnings.append(
                data_quality_warning(
                    key="partial_garmin_today",
                    severity="watch",
                    title="Today's Garmin data is partial",
                    message=(
                        "Today's Garmin row is partial. Readiness should use the "
                        "previous completed day."
                    ),
                )
            )

    return warnings


def build_stats2_charts(stats: dict[str, Any]) -> dict[str, Any]:
    workouts = stats["workouts"]
    exercise_stats = stats["exercise_stats"]

    best_strength = [
        exercise
        for exercise in exercise_stats
        if exercise["best_e1rm"] is not None and exercise["best_set"]
    ]
    best_strength.sort(
        key=lambda exercise: exercise["best_e1rm"],
        reverse=True,
    )

    max_e1rm = max(
        [exercise["best_e1rm"] for exercise in best_strength],
        default=0,
    )

    max_exercise_volume = max(
        [exercise["total_volume"] for exercise in exercise_stats],
        default=0,
    )

    return {
        "volume": build_line_chart_series(workouts, "total_volume"),
        "volume_kg": build_line_chart_series(workouts, "total_volume_kg"),
        "bodyweight_reps": build_line_chart_series(workouts, "bodyweight_reps"),
        "duration_seconds": build_line_chart_series(workouts, "duration_seconds"),
        "distance_m": build_line_chart_series(workouts, "distance_m"),
        "intensity": build_line_chart_series(workouts, "avg_intensity"),
        "rpe": build_line_chart_series(workouts, "session_rpe", max_value=10),
        "back": build_line_chart_series(workouts, "lower_back_pain", max_value=10),
        "scatter": build_scatter_points(workouts),
        "back_calendar": build_calendar_heatmap(workouts, "lower_back_pain"),
        "rpe_calendar": build_calendar_heatmap(workouts, "session_rpe"),
        "load": build_line_chart_series(workouts, "load_score"),
        "load_calendar": build_calendar_heatmap(workouts, "load_score"),
        "compound": build_line_chart_series(workouts, "compound_score"),
        "back_stress": build_line_chart_series(workouts, "back_stress_score"),
        "sparkbars": {
            "volume": build_sparkbar(
                [workout["total_volume"] for workout in workouts],
                width=14,
            ),
            "volume_kg": build_sparkbar(
                [workout["total_volume_kg"] for workout in workouts],
                width=14,
            ),
            "bodyweight_reps": build_sparkbar(
                [workout["bodyweight_reps"] for workout in workouts],
                width=14,
            ),
            "intensity": build_sparkbar(
                [workout["avg_intensity"] for workout in workouts],
                width=14,
            ),
            "rpe": build_sparkbar(
                [workout["session_rpe"] for workout in workouts],
                width=14,
                max_value=10,
            ),
            "back": build_sparkbar(
                [workout["lower_back_pain"] for workout in workouts],
                width=14,
                max_value=10,
            ),
            "load": build_sparkbar(
                [workout["load_score"] for workout in workouts],
                width=14,
            ),
            "compound": build_sparkbar(
                [workout["compound_score"] for workout in workouts],
                width=14,
            ),
            "back_stress": build_sparkbar(
                [workout["back_stress_score"] for workout in workouts],
                width=14,
            ),
        },
        "best_strength": best_strength,
        "max_e1rm": max_e1rm,
        "max_exercise_volume": max_exercise_volume,
    }


def build_stats(limit: int | None = 30) -> dict[str, Any]:
    with get_db() as conn:
        if limit is None:
            workouts = conn.execute(
                """
                WITH latest_garmin AS (
                    SELECT
                        date,
                        resting_heart_rate,
                        hrv_ms,
                        stress_avg,
                        body_battery_start,
                        body_battery_end,
                        steps,
                        synced_at
                    FROM garmin_daily_metrics
                    ORDER BY date DESC
                    LIMIT 1
                )
                SELECT
                    w.*,
                    latest_garmin.date AS latest_garmin_date,
                    latest_garmin.resting_heart_rate AS latest_garmin_resting_heart_rate,
                    latest_garmin.hrv_ms AS latest_garmin_hrv_ms,
                    latest_garmin.stress_avg AS latest_garmin_stress_avg,
                    latest_garmin.body_battery_start AS latest_garmin_body_battery_start,
                    latest_garmin.body_battery_end AS latest_garmin_body_battery_end,
                    latest_garmin.steps AS latest_garmin_steps,
                    latest_garmin.synced_at AS latest_garmin_synced_at
                FROM workouts w
                LEFT JOIN latest_garmin ON 1 = 1
                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()
        else:
            workouts = conn.execute(
                """
                WITH latest_garmin AS (
                    SELECT
                        date,
                        resting_heart_rate,
                        hrv_ms,
                        stress_avg,
                        body_battery_start,
                        body_battery_end,
                        steps,
                        synced_at
                    FROM garmin_daily_metrics
                    ORDER BY date DESC
                    LIMIT 1
                )
                SELECT *
                FROM (
                    SELECT
                        w.*,
                        latest_garmin.date AS latest_garmin_date,
                        latest_garmin.resting_heart_rate AS latest_garmin_resting_heart_rate,
                        latest_garmin.hrv_ms AS latest_garmin_hrv_ms,
                        latest_garmin.stress_avg AS latest_garmin_stress_avg,
                        latest_garmin.body_battery_start AS latest_garmin_body_battery_start,
                        latest_garmin.body_battery_end AS latest_garmin_body_battery_end,
                        latest_garmin.steps AS latest_garmin_steps,
                        latest_garmin.synced_at AS latest_garmin_synced_at
                    FROM workouts w
                    LEFT JOIN latest_garmin ON 1 = 1
                    ORDER BY w.created_at DESC, w.id DESC
                    LIMIT ?
                )
                ORDER BY created_at ASC, id ASC
                """,
                (limit,),
            ).fetchall()

    workout_ids = [int(workout["id"]) for workout in workouts]
    details_by_workout = get_workout_details_batch(workout_ids)
    e1rm_baselines_by_workout = build_e1rm_baselines_by_workout(
        workouts=list(workouts),
        details_by_workout=details_by_workout,
    )

    weight_baselines_by_workout = build_weight_baselines_by_workout(
        workouts=list(workouts),
        details_by_workout=details_by_workout,
    )
    profiles_by_key = runtime_profiles_by_key()

    selected_week_starts = build_selected_week_starts(
        list(workouts)
    )

    workout_items = []
    exercise_stats: dict[int, dict[str, Any]] = {}
    exercise_progress: dict[int, dict[str, Any]] = {}
    exercise_rep_progress: dict[int, dict[str, Any]] = {}
    exercise_weekly_workload: dict[int, dict[str, Any]] = {}
    zero_kg_weighted_set_count = 0

    for workout in workouts:
        current_workout_id = int(workout["id"])
        details = details_by_workout.get(current_workout_id, [])
        zero_kg_weighted_set_count += sum(
            1
            for item in details
            if item["measurement_type"] == "weighted_reps"
            for set_row in item["sets"]
            if float(set_row["weight"]) == 0 and int(set_row["reps"]) > 0
        )

        total_volume = sum(item["total_volume"] for item in details)
        total_volume_kg = sum(item["total_volume_kg"] for item in details)
        bodyweight_reps = sum(item["bodyweight_reps"] for item in details)
        duration_seconds = sum(item["duration_seconds"] for item in details)
        distance_m = sum(item["distance_m"] for item in details)
        weighted_reps = sum(
            int(set_row["reps"])
            for item in details
            for set_row in item["sets"]
            if float(set_row["weight"]) > 0
        )
        total_reps = sum(item["total_reps"] for item in details)
        total_sets = sum(len(item["sets"]) for item in details)

        avg_intensity = None
        if total_reps:
            avg_intensity = total_volume / total_reps
        avg_kg_per_rep = None
        if weighted_reps:
            avg_kg_per_rep = total_volume_kg / weighted_reps

        load_metrics = calculate_workout_load_metrics(
            workout_exercises=details,
            session_rpe=workout["session_rpe"],
            as_of_created_at=workout["created_at"],
            as_of_workout_id=current_workout_id,
            best_e1rm_by_exercise=e1rm_baselines_by_workout.get(
                current_workout_id,
                {},
            ),
            profiles_by_key=profiles_by_key,
        )

        workout_items.append(
            {
                "id": current_workout_id,
                "date": workout["created_at"][:10],
                "created_at": workout["created_at"],
                "total_volume": total_volume,
                "total_volume_kg": total_volume_kg,
                "bodyweight_reps": bodyweight_reps,
                "duration_seconds": duration_seconds,
                "distance_m": distance_m,
                "weighted_reps": weighted_reps,
                "total_reps": total_reps,
                "total_sets": total_sets,
                "avg_intensity": avg_intensity,
                "avg_kg_per_rep": avg_kg_per_rep,
                "session_rpe": workout["session_rpe"],
                "lower_back_pain": workout["lower_back_pain"],
                "load_score": load_metrics["load_score"],
                "load_label": load_metrics["load_label"],
                "compound_score": load_metrics["compound_score"],
                "intensity_score": load_metrics["intensity_score"],
                "back_stress_score": load_metrics["back_stress_score"],
            }
        )

        workout_strength_best: dict[int, dict[str, Any]] = {}
        workout_rep_best: dict[int, dict[str, Any]] = {}

        for item in details:
            exercise_id = int(item["exercise_id"])
            exercise_name = item["exercise_name"]
            measurement_type = str(item.get("measurement_type") or "weighted_reps")

            if exercise_id not in exercise_stats:
                exercise_stats[exercise_id] = {
                    "exercise_id": exercise_id,
                    "name": exercise_name,
                    "total_volume": 0.0,
                    "total_volume_kg": 0.0,
                    "bodyweight_reps": 0,
                    "duration_seconds": 0,
                    "distance_m": 0,
                    "weighted_reps": 0,
                    "total_reps": 0,
                    "total_sets": 0,
                    "best_e1rm": None,
                    "best_set": None,
                }

            stats = exercise_stats[exercise_id]
            stats["total_volume"] += item["total_volume"]
            stats["total_volume_kg"] += item["total_volume_kg"]
            stats["bodyweight_reps"] += item["bodyweight_reps"]
            stats["duration_seconds"] += item["duration_seconds"]
            stats["distance_m"] += item["distance_m"]
            stats["weighted_reps"] += sum(
                int(set_row["reps"])
                for set_row in item["sets"]
                if float(set_row["weight"]) > 0
            )
            stats["total_reps"] += item["total_reps"]
            stats["total_sets"] += len(item["sets"])

            week_start = workout_week_start(
                str(workout["created_at"])
            )

            weekly_exercise = exercise_weekly_workload.setdefault(
                exercise_id,
                {
                    "exercise_id": exercise_id,
                    "name": exercise_name,
                    "weeks": {},
                },
            )

            week_bucket = weekly_exercise["weeks"].setdefault(
                week_start,
                {
                    "sets": 0,
                    "reps": 0,
                    "volume": 0.0,
                    "volume_kg": 0.0,
                    "bodyweight_reps": 0,
                    "duration_seconds": 0,
                    "distance_m": 0,
                    "workout_ids": set(),
                },
            )

            week_bucket["sets"] += len(item["sets"])
            week_bucket["reps"] += int(item["total_reps"])
            week_bucket["volume"] += float(item["total_volume"])
            week_bucket["volume_kg"] += float(item["total_volume_kg"])
            week_bucket["bodyweight_reps"] += int(item["bodyweight_reps"])
            week_bucket["duration_seconds"] += int(item["duration_seconds"])
            week_bucket["distance_m"] += int(item["distance_m"])
            week_bucket["workout_ids"].add(current_workout_id)

            for set_row in item["sets"]:
                weight = float(set_row["weight"])
                reps = int(set_row["reps"])

                if weight > 0 and reps > 0:
                    exercise_rep_best = workout_rep_best.setdefault(
                        exercise_id,
                        {
                            "name": exercise_name,
                            "targets": {},
                        },
                    )

                    previous_weight = exercise_rep_best["targets"].get(reps)

                    if previous_weight is None or weight > previous_weight:
                        exercise_rep_best["targets"][reps] = weight

                e1rm = estimated_1rm(weight, reps, measurement_type)

                if e1rm is None:
                    continue

                current_workout_best = workout_strength_best.get(exercise_id)

                if (
                    current_workout_best is None
                    or e1rm > current_workout_best["e1rm"]
                ):
                    workout_strength_best[exercise_id] = {
                        "exercise_id": exercise_id,
                        "name": exercise_name,
                        "e1rm": e1rm,
                        "weight": weight,
                        "reps": reps,
                    }

                if stats["best_e1rm"] is None or e1rm > stats["best_e1rm"]:
                    stats["best_e1rm"] = e1rm
                    stats["best_set"] = {
                        "weight": weight,
                        "reps": reps,
                        "workout_id": current_workout_id,
                        "date": workout["created_at"][:10],
                    }

        historical_baselines = e1rm_baselines_by_workout.get(
            current_workout_id,
            {},
        )

        for exercise_id, point in workout_strength_best.items():
            previous_best = historical_baselines.get(exercise_id)

            rolling_best = point["e1rm"]
            if previous_best is not None:
                rolling_best = max(previous_best, point["e1rm"])

            progress = exercise_progress.setdefault(
                exercise_id,
                {
                    "exercise_id": exercise_id,
                    "name": point["name"],
                    "points": [],
                },
            )

            progress["points"].append(
                {
                    "workout_id": current_workout_id,
                    "date": workout["created_at"][:10],
                    "e1rm": point["e1rm"],
                    "rolling_best": rolling_best,
                    "weight": point["weight"],
                    "reps": point["reps"],
                    # The first-ever valid result establishes the baseline.
                    # Only later improvements are marked as PRs.
                    "is_pr": (
                        previous_best is not None
                        and point["e1rm"] > previous_best + 1e-9
                    ),
                }
            )

        historical_weight_baselines = (
            weight_baselines_by_workout.get(
                current_workout_id,
                {},
            )
        )

        for exercise_id, workout_progress in workout_rep_best.items():
            progress = exercise_rep_progress.setdefault(
                exercise_id,
                {
                    "exercise_id": exercise_id,
                    "name": workout_progress["name"],
                    "rep_targets": {},
                },
            )

            exercise_history = historical_weight_baselines.get(
                exercise_id,
                {},
            )

            for reps, weight in workout_progress["targets"].items():
                previous_best = exercise_history.get(reps)

                rolling_best = weight
                if previous_best is not None:
                    rolling_best = max(previous_best, weight)

                target = progress["rep_targets"].setdefault(
                    reps,
                    {
                        "reps": reps,
                        "points": [],
                    },
                )

                target["points"].append(
                    {
                        "workout_id": current_workout_id,
                        "date": workout["created_at"][:10],
                        "weight": weight,
                        "rolling_best": rolling_best,
                        # The first result establishes the baseline.
                        "is_pr": (
                            previous_best is not None
                            and weight > previous_best + 1e-9
                        ),
                    }
                )

    total_volume = sum(item["total_volume"] for item in workout_items)
    total_volume_kg = sum(item["total_volume_kg"] for item in workout_items)
    bodyweight_reps = sum(item["bodyweight_reps"] for item in workout_items)
    duration_seconds = sum(item["duration_seconds"] for item in workout_items)
    distance_m = sum(item["distance_m"] for item in workout_items)
    weighted_reps = sum(item["weighted_reps"] for item in workout_items)
    total_reps = sum(item["total_reps"] for item in workout_items)
    total_sets = sum(item["total_sets"] for item in workout_items)

    rpe_values = [
        int(item["session_rpe"])
        for item in workout_items
        if item["session_rpe"] is not None
    ]
    back_values = [
        int(item["lower_back_pain"])
        for item in workout_items
        if item["lower_back_pain"] is not None
    ]

    total_load_score = sum(item["load_score"] for item in workout_items)
    total_compound_score = sum(item["compound_score"] for item in workout_items)
    total_back_stress_score = sum(item["back_stress_score"] for item in workout_items)

    intensity_scores = [
        float(item["intensity_score"])
        for item in workout_items
        if item["intensity_score"] is not None
    ]

    sorted_exercise_stats = sorted(
        exercise_stats.values(),
        key=lambda item: item["total_volume"],
        reverse=True,
    )

    sorted_exercise_weekly_workload = []

    for exercise in sorted_exercise_stats:
        exercise_id = int(exercise["exercise_id"])

        weekly_exercise = exercise_weekly_workload.get(
            exercise_id
        )

        if weekly_exercise is None:
            continue

        weeks = []

        for week_start in selected_week_starts:
            bucket = weekly_exercise["weeks"].get(week_start)

            if bucket is None:
                weeks.append(
                    {
                        "week_start": week_start,
                        "sets": 0,
                        "reps": 0,
                        "volume": 0.0,
                        "volume_kg": 0.0,
                        "bodyweight_reps": 0,
                        "duration_seconds": 0,
                        "distance_m": 0,
                        "workouts": 0,
                    }
                )
                continue

            weeks.append(
                {
                    "week_start": week_start,
                    "sets": int(bucket["sets"]),
                    "reps": int(bucket["reps"]),
                    "volume": float(bucket["volume"]),
                    "volume_kg": float(bucket["volume_kg"]),
                    "bodyweight_reps": int(bucket["bodyweight_reps"]),
                    "duration_seconds": int(bucket["duration_seconds"]),
                    "distance_m": int(bucket["distance_m"]),
                    "workouts": len(bucket["workout_ids"]),
                }
            )

        sorted_exercise_weekly_workload.append(
            {
                "exercise_id": exercise_id,
                "name": weekly_exercise["name"],
                "weeks": weeks,
            }
        )

    sorted_exercise_progress = [
        exercise_progress[item["exercise_id"]]
        for item in sorted_exercise_stats
        if item["exercise_id"] in exercise_progress
    ]

    sorted_exercise_rep_progress = []

    for exercise in sorted_exercise_stats:
        exercise_id = int(exercise["exercise_id"])
        progress = exercise_rep_progress.get(exercise_id)

        if progress is None:
            continue

        sorted_exercise_rep_progress.append(
            {
                "exercise_id": exercise_id,
                "name": progress["name"],
                "rep_targets": sorted(
                    progress["rep_targets"].values(),
                    key=lambda target: target["reps"],
                ),
            }
        )

    summary_payload = {
        "workout_count": len(workout_items),
        "total_volume": total_volume,
        "total_volume_kg": total_volume_kg,
        "bodyweight_reps": bodyweight_reps,
        "duration_seconds": duration_seconds,
        "distance_m": distance_m,
        "weighted_reps": weighted_reps,
        "total_reps": total_reps,
        "total_sets": total_sets,
        "avg_intensity": total_volume / total_reps if total_reps else None,
        "avg_kg_per_rep": (
            total_volume_kg / weighted_reps
            if weighted_reps
            else None
        ),
        "avg_rpe": sum(rpe_values) / len(rpe_values) if rpe_values else None,
        "avg_back_pain": sum(back_values) / len(back_values) if back_values else None,
        "total_load_score": total_load_score,
        "avg_load_score": total_load_score / len(workout_items) if workout_items else None,
        "total_compound_score": total_compound_score,
        "avg_compound_score": total_compound_score / len(workout_items) if workout_items else None,
        "total_back_stress_score": total_back_stress_score,
        "avg_back_stress_score": total_back_stress_score / len(workout_items) if workout_items else None,
        "avg_relative_intensity": (
            sum(intensity_scores) / len(intensity_scores)
            if intensity_scores
            else None
        ),
    }

    return {
        "workouts": workout_items,
        "exercise_stats": sorted_exercise_stats,
        "exercise_progress": sorted_exercise_progress,
        "exercise_rep_progress": sorted_exercise_rep_progress,
        "exercise_weekly_workload": (
            sorted_exercise_weekly_workload
        ),
        "summary": summary_payload,
        "data_quality_warnings": build_data_quality_warnings(
            workouts=workout_items,
            summary=summary_payload,
            zero_kg_weighted_set_count=zero_kg_weighted_set_count,
            latest_garmin_metric=latest_garmin_metric_from_workouts(list(workouts)),
        ),
        "training_load": build_training_load_summary(
            workout_items,
            today=app_today(),
        ),
    }

def exercise_set_payload(set_row: Any) -> dict[str, Any]:
    return {
        "id": int(set_row["id"]),
        "workout_exercise_id": int(set_row["workout_exercise_id"]),
        "set_number": int(set_row["set_number"]),
        "weight": float(set_row["weight"]),
        "reps": int(set_row["reps"]),
        "created_at": str(set_row["created_at"]),
    }


def score_exercise_set(
    weight: float,
    reps: int,
    measurement_type: str = "weighted_reps",
) -> float:
    e1rm = estimated_1rm(weight, reps, measurement_type)
    if e1rm is not None:
        return e1rm
    if weight > 0:
        return weight * reps
    return float(reps)


def empty_exercise_summary() -> dict[str, Any]:
    return {
        "workout_count": 0,
        "total_volume": 0.0,
        "total_volume_kg": 0.0,
        "total_reps": 0,
        "total_sets": 0,
        "bodyweight_reps": 0,
        "duration_seconds": 0,
        "distance_m": 0,
        "weighted_reps": 0,
        "avg_kg_per_rep": None,
        "avg_intensity": None,
        "best_weight": None,
        "best_reps": None,
        "best_e1rm": None,
        "best_set": None,
        "pr_count": 0,
        "first_workout_at": None,
        "latest_workout_at": None,
    }


def build_exercise_pr_baselines(
    exercise_id: int,
    selected_workout_ids: set[int],
    max_workout: Any | None,
) -> dict[int, dict[str, Any]]:
    if max_workout is None or not selected_workout_ids:
        return {}

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT
                w.id AS workout_id,
                w.created_at,
                COALESCE(we.measurement_type, e.measurement_type, 'weighted_reps') AS measurement_type,
                se.weight,
                se.reps
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
            JOIN exercises e ON e.id = we.exercise_id
            JOIN workouts w ON w.id = we.workout_id
            WHERE we.exercise_id = ?
              AND (
                    w.created_at < ?
                    OR (w.created_at = ? AND w.id <= ?)
              )
            ORDER BY w.created_at ASC, w.id ASC, se.set_number ASC, se.id ASC
            """,
            (
                exercise_id,
                workout_created_at(max_workout),
                workout_created_at(max_workout),
                workout_id(max_workout),
            ),
        ).fetchall()

    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        current_workout_id = int(row["workout_id"])
        workout = grouped.setdefault(
            current_workout_id,
            {
                "created_at": str(row["created_at"]),
                "max_weight": None,
                "max_reps": None,
                "best_e1rm": None,
                "total_volume": 0.0,
                "bodyweight_reps": 0,
                "duration_seconds": 0,
                "distance_m": 0,
            },
        )

        weight = float(row["weight"])
        reps = int(row["reps"])
        measurement_type = str(row["measurement_type"] or "weighted_reps")
        workout["total_volume"] += weight * reps
        if measurement_type in {"bodyweight_reps", "reps_only"}:
            workout["bodyweight_reps"] += reps
        elif measurement_type in {"loaded_carry_time", "duration_only"}:
            workout["duration_seconds"] += reps
        elif measurement_type == "loaded_carry_distance":
            workout["distance_m"] += reps

        if workout["max_weight"] is None or weight > workout["max_weight"]:
            workout["max_weight"] = weight

        if workout["max_reps"] is None or reps > workout["max_reps"]:
            workout["max_reps"] = reps

        e1rm = estimated_1rm(weight, reps, measurement_type)
        if e1rm is not None:
            if workout["best_e1rm"] is None or e1rm > workout["best_e1rm"]:
                workout["best_e1rm"] = e1rm

    prior_best = {
        "max_weight": None,
        "max_reps": None,
        "best_e1rm": None,
        "best_volume": None,
        "best_bodyweight_reps": None,
        "best_duration_seconds": None,
        "best_distance_m": None,
    }
    baselines: dict[int, dict[str, Any]] = {}

    for current_workout_id, workout in sorted(
        grouped.items(),
        key=lambda item: (item[1]["created_at"], item[0]),
    ):
        if current_workout_id in selected_workout_ids:
            baselines[current_workout_id] = dict(prior_best)

        max_weight = workout["max_weight"]
        if max_weight is not None:
            if prior_best["max_weight"] is None or max_weight > prior_best["max_weight"]:
                prior_best["max_weight"] = max_weight

        max_reps = workout["max_reps"]
        if max_reps is not None:
            if prior_best["max_reps"] is None or max_reps > prior_best["max_reps"]:
                prior_best["max_reps"] = max_reps

        best_e1rm = workout["best_e1rm"]
        if best_e1rm is not None:
            if prior_best["best_e1rm"] is None or best_e1rm > prior_best["best_e1rm"]:
                prior_best["best_e1rm"] = best_e1rm

        total_volume = float(workout["total_volume"])
        if prior_best["best_volume"] is None or total_volume > prior_best["best_volume"]:
            prior_best["best_volume"] = total_volume

        bodyweight_reps = int(workout["bodyweight_reps"])
        if bodyweight_reps > 0:
            if (
                prior_best["best_bodyweight_reps"] is None
                or bodyweight_reps > prior_best["best_bodyweight_reps"]
            ):
                prior_best["best_bodyweight_reps"] = bodyweight_reps

        duration_seconds = int(workout["duration_seconds"])
        if duration_seconds > 0:
            if (
                prior_best["best_duration_seconds"] is None
                or duration_seconds > prior_best["best_duration_seconds"]
            ):
                prior_best["best_duration_seconds"] = duration_seconds

        distance_m = int(workout["distance_m"])
        if distance_m > 0:
            if (
                prior_best["best_distance_m"] is None
                or distance_m > prior_best["best_distance_m"]
            ):
                prior_best["best_distance_m"] = distance_m

    return baselines


def build_exercise_stats(
    exercise_id: int,
    limit: int | None = 30,
) -> dict[str, Any] | None:
    with get_db() as conn:
        exercise = conn.execute(
            """
            SELECT id, name, is_active, sort_order, profile_key, measurement_type, reps_unit
            FROM exercises
            WHERE id = ?
            """,
            (exercise_id,),
        ).fetchone()

        if exercise is None:
            return None

        measurement = normalize_measurement_settings(
            measurement_type=exercise["measurement_type"],
            reps_unit=exercise["reps_unit"],
            exercise_name=exercise["name"],
        )
        measurement_type = measurement["measurement_type"]
        reps_unit = measurement["reps_unit"]

        if limit is None:
            workouts = conn.execute(
                """
                SELECT *
                FROM workouts w
                WHERE EXISTS (
                    SELECT 1
                    FROM workout_exercises we
                    WHERE we.workout_id = w.id
                      AND we.exercise_id = ?
                )
                ORDER BY w.created_at ASC, w.id ASC
                """,
                (exercise_id,),
            ).fetchall()
        else:
            workouts = conn.execute(
                """
                SELECT *
                FROM (
                    SELECT w.*
                    FROM workouts w
                    WHERE EXISTS (
                        SELECT 1
                        FROM workout_exercises we
                        WHERE we.workout_id = w.id
                          AND we.exercise_id = ?
                    )
                    ORDER BY w.created_at DESC, w.id DESC
                    LIMIT ?
                )
                ORDER BY created_at ASC, id ASC
                """,
                (exercise_id, limit),
            ).fetchall()

    workout_ids = [workout_id(workout) for workout in workouts]
    selected_workout_ids = set(workout_ids)
    details_by_workout = get_workout_details_batch(workout_ids)
    e1rm_baselines_by_workout = build_e1rm_baselines_by_workout(
        workouts=list(workouts),
        details_by_workout=details_by_workout,
    )
    pr_baselines_by_workout = build_exercise_pr_baselines(
        exercise_id=exercise_id,
        selected_workout_ids=selected_workout_ids,
        max_workout=workouts[-1] if workouts else None,
    )

    profile_key = str(exercise["profile_key"] or "accessory")
    profile = next(
        (
            item
            for item in list_exercise_profiles()
            if item["key"] == profile_key
        ),
        {
            "key": profile_key,
            "label": profile_key,
            "category": "accessory",
        },
    )

    history: list[dict[str, Any]] = []
    strength_points: list[dict[str, Any]] = []
    per_workout_sets: list[dict[str, Any]] = []
    source_workout_ids: list[int] = []

    summary = empty_exercise_summary()
    best_set_score = -1.0
    pr_count = 0

    for workout in workouts:
        current_workout_id = workout_id(workout)
        exercise_items = [
            item
            for item in details_by_workout.get(current_workout_id, [])
            if int(item["exercise_id"]) == exercise_id
        ]
        sets = [
            set_row
            for item in exercise_items
            for set_row in item["sets"]
        ]
        set_payloads = [exercise_set_payload(set_row) for set_row in sets]
        workout_measurement = (
            exercise_items[0]
            if exercise_items
            else {"measurement_type": measurement_type, "reps_unit": reps_unit}
        )
        workout_measurement_type = str(
            workout_measurement.get("measurement_type") or measurement_type
        )
        workout_reps_unit = str(workout_measurement.get("reps_unit") or reps_unit)

        derived_metrics = derive_set_metrics(sets, workout_measurement_type)
        total_volume = float(derived_metrics["total_volume_kg"])
        total_volume_kg = total_volume
        total_reps = sum(int(set_row["reps"]) for set_row in sets)
        total_sets = len(sets)
        bodyweight_reps = int(derived_metrics["bodyweight_reps"])
        duration_seconds = int(derived_metrics["duration_seconds"])
        distance_m = int(derived_metrics["distance_m"])
        weighted_reps = sum(
            int(set_row["reps"])
            for set_row in sets
            if float(set_row["weight"]) > 0
        )
        avg_kg_per_rep = total_volume_kg / weighted_reps if weighted_reps else None
        best_weight = None
        best_reps = None
        best_e1rm = None
        best_set = None
        workout_best_score = -1.0

        for set_row in sets:
            weight = float(set_row["weight"])
            reps = int(set_row["reps"])

            if best_weight is None or weight > best_weight:
                best_weight = weight
            if best_reps is None or reps > best_reps:
                best_reps = reps

            e1rm = estimated_1rm(weight, reps, workout_measurement_type)
            if e1rm is not None:
                if best_e1rm is None or e1rm > best_e1rm:
                    best_e1rm = e1rm

            set_score = score_exercise_set(weight, reps, workout_measurement_type)
            if set_score > workout_best_score:
                workout_best_score = set_score
                best_set = {
                    **exercise_set_payload(set_row),
                    "volume": weight * reps,
                    "e1rm": e1rm,
                }

            if set_score > best_set_score:
                best_set_score = set_score
                summary["best_set"] = {
                    **exercise_set_payload(set_row),
                    "workout_id": current_workout_id,
                    "date": str(workout["created_at"])[:10],
                    "volume": weight * reps,
                    "e1rm": e1rm,
                }

        summary["total_volume"] += total_volume
        summary["total_volume_kg"] += total_volume_kg
        summary["total_reps"] += total_reps
        summary["total_sets"] += total_sets
        summary["bodyweight_reps"] += bodyweight_reps
        summary["duration_seconds"] += duration_seconds
        summary["distance_m"] += distance_m
        summary["weighted_reps"] += weighted_reps

        if best_weight is not None:
            if summary["best_weight"] is None or best_weight > summary["best_weight"]:
                summary["best_weight"] = best_weight
        if best_reps is not None:
            if summary["best_reps"] is None or best_reps > summary["best_reps"]:
                summary["best_reps"] = best_reps
        if best_e1rm is not None:
            if summary["best_e1rm"] is None or best_e1rm > summary["best_e1rm"]:
                summary["best_e1rm"] = best_e1rm

        prior = pr_baselines_by_workout.get(current_workout_id, {})
        pr_flags: list[str] = []

        if (
            best_weight is not None
            and best_weight > 0
            and prior.get("max_weight") is not None
            and best_weight > float(prior["max_weight"]) + 1e-9
        ):
            pr_flags.append("Weight PR")

        if (
            best_reps is not None
            and prior.get("max_reps") is not None
            and best_reps > int(prior["max_reps"])
        ):
            pr_flags.append("Rep PR")

        previous_best_e1rm = e1rm_baselines_by_workout.get(
            current_workout_id,
            {},
        ).get(exercise_id)

        if (
            best_e1rm is not None
            and previous_best_e1rm is not None
            and best_e1rm > previous_best_e1rm + 1e-9
        ):
            pr_flags.append("e1RM PR")

        if workout_measurement_type == "weighted_reps" and (
            total_volume > 0
            and prior.get("best_volume") is not None
            and total_volume > float(prior["best_volume"]) + 1e-9
        ):
            pr_flags.append("Volume PR")

        if workout_measurement_type in {"bodyweight_reps", "reps_only"} and (
            bodyweight_reps > 0
            and prior.get("best_bodyweight_reps") is not None
            and bodyweight_reps > int(prior["best_bodyweight_reps"])
        ):
            pr_flags.append("Total reps PR")

        if workout_measurement_type in {"loaded_carry_time", "duration_only"} and (
            duration_seconds > 0
            and prior.get("best_duration_seconds") is not None
            and duration_seconds > int(prior["best_duration_seconds"])
        ):
            pr_flags.append("Duration PR")

        if workout_measurement_type == "loaded_carry_distance" and (
            distance_m > 0
            and prior.get("best_distance_m") is not None
            and distance_m > int(prior["best_distance_m"])
        ):
            pr_flags.append("Distance PR")

        rolling_best_e1rm = best_e1rm
        if previous_best_e1rm is not None:
            rolling_best_e1rm = (
                max(previous_best_e1rm, best_e1rm)
                if best_e1rm is not None
                else previous_best_e1rm
            )

        workout_entry = {
            "id": current_workout_id,
            "workout_id": current_workout_id,
            "date": str(workout["created_at"])[:10],
            "created_at": str(workout["created_at"]),
            "workout_exercise_ids": [
                int(item["workout_exercise_id"])
                for item in exercise_items
            ],
            "sets": set_payloads,
            "total_volume": total_volume,
            "total_volume_kg": total_volume_kg,
            "total_reps": total_reps,
            "total_sets": total_sets,
            "bodyweight_reps": bodyweight_reps,
            "duration_seconds": duration_seconds,
            "distance_m": distance_m,
            "weighted_reps": weighted_reps,
            "avg_kg_per_rep": avg_kg_per_rep,
            "avg_intensity": total_volume / total_reps if total_reps else None,
            "measurement_type": workout_measurement_type,
            "reps_unit": workout_reps_unit,
            "best_weight": best_weight,
            "best_reps": best_reps,
            "best_e1rm": best_e1rm,
            "rolling_best_e1rm": rolling_best_e1rm,
            "best_set": best_set,
            "pr_flags": pr_flags,
        }

        history.append(workout_entry)
        per_workout_sets.append(
            {
                "workout_id": current_workout_id,
                "date": workout_entry["date"],
                "sets": set_payloads,
            }
        )
        source_workout_ids.append(current_workout_id)
        pr_count += len(pr_flags)

        if best_e1rm is not None:
            strength_points.append(
                {
                    "workout_id": current_workout_id,
                    "date": workout_entry["date"],
                    "e1rm": best_e1rm,
                    "rolling_best": rolling_best_e1rm,
                    "weight": best_set["weight"] if best_set else None,
                    "reps": best_set["reps"] if best_set else None,
                    "is_pr": "e1RM PR" in pr_flags,
                }
            )

    summary["workout_count"] = len(history)
    summary["avg_intensity"] = (
        summary["total_volume"] / summary["total_reps"]
        if summary["total_reps"]
        else None
    )
    summary["avg_kg_per_rep"] = (
        summary["total_volume_kg"] / summary["weighted_reps"]
        if summary["weighted_reps"]
        else None
    )
    summary["pr_count"] = pr_count
    summary["first_workout_at"] = history[0]["created_at"] if history else None
    summary["latest_workout_at"] = history[-1]["created_at"] if history else None

    return {
        "limit": "all" if limit is None else limit,
        "exercise": {
            "id": int(exercise["id"]),
            "name": str(exercise["name"]),
            "is_active": bool(exercise["is_active"]),
            "sort_order": int(exercise["sort_order"]),
            "profile_key": profile_key,
            "measurement_type": measurement_type,
            "reps_unit": reps_unit,
        },
        "profile": profile,
        "summary": summary,
        "latest": history[-1] if history else None,
        "history": history,
        "per_workout_sets": per_workout_sets,
        "trend": {
            "volume": build_line_chart_series(history, "total_volume"),
            "volume_kg": build_line_chart_series(history, "total_volume_kg"),
            "bodyweight_reps": build_line_chart_series(history, "bodyweight_reps"),
            "duration_seconds": build_line_chart_series(history, "duration_seconds"),
            "distance_m": build_line_chart_series(history, "distance_m"),
            "best_e1rm": build_line_chart_series(history, "best_e1rm"),
            "reps": build_line_chart_series(history, "total_reps"),
        },
        "strength_progress": {
            "exercise_id": exercise_id,
            "name": str(exercise["name"]),
            "points": strength_points,
        },
        "source_workout_ids": source_workout_ids,
    }
