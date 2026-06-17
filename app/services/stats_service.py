from datetime import date, timedelta
from typing import Any

from app.db import get_db
from app.repositories.workouts import get_workout_details_batch
from app.services.analysis_service import (
    calculate_workout_load_metrics as calculate_load_metrics,
    estimated_1rm,
)


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
                se.weight,
                se.reps
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
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
        e1rm = estimated_1rm(weight, reps)

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
) -> dict[str, Any]:
    if best_e1rm_by_exercise is not None:
        return calculate_load_metrics(
            workout_exercises=workout_exercises,
            session_rpe=session_rpe,
            best_e1rm_by_exercise=best_e1rm_by_exercise,
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
    )


def workout_created_at(workout: Any) -> str:
    return str(workout["created_at"])


def workout_id(workout: Any) -> int:
    return int(workout["id"])


def workout_sort_key(workout: Any) -> tuple[str, int]:
    return (workout_created_at(workout), workout_id(workout))


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
                se.weight,
                se.reps
            FROM set_entries se
            JOIN workout_exercises we ON we.id = se.workout_exercise_id
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
            e1rm = estimated_1rm(float(row["weight"]), int(row["reps"]))
            if e1rm is not None:
                if exercise_id not in best_by_exercise or e1rm > best_by_exercise[exercise_id]:
                    best_by_exercise[exercise_id] = e1rm

            row_index += 1

        baselines_by_workout[workout_id(workout)] = dict(best_by_exercise)

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

                e1rm = estimated_1rm(weight, reps)
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
                    se.weight,
                    se.reps
                FROM set_entries se
                JOIN workout_exercises we ON we.id = se.workout_exercise_id
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

                e1rm = estimated_1rm(weight, reps)
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
        if workout["total_volume"] > 0
        and workout["lower_back_pain"] is not None
    ]

    if not valid_items:
        return {
            "points": [],
            "max_volume": None,
        }

    max_volume = max(float(item["total_volume"]) for item in valid_items)
    if max_volume <= 0:
        max_volume = 1.0

    points = []

    for workout in valid_items:
        volume = float(workout["total_volume"])
        back = float(workout["lower_back_pain"])

        points.append(
            {
                "x": min(100, max(0, volume / max_volume * 100)),
                "y": 100 - min(100, max(0, back / 10 * 100)),
                "volume": volume,
                "back": back,
                "date": workout["date"],
                "workout_id": workout["id"],
            }
        )

    return {
        "points": points,
        "max_volume": max_volume,
    }


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
                SELECT *
                FROM workouts
                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()
        else:
            workouts = conn.execute(
                """
                SELECT *
                FROM (
                    SELECT *
                    FROM workouts
                    ORDER BY created_at DESC, id DESC
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

    workout_items = []
    exercise_stats: dict[int, dict[str, Any]] = {}

    for workout in workouts:
        current_workout_id = int(workout["id"])
        details = details_by_workout.get(current_workout_id, [])

        total_volume = sum(item["total_volume"] for item in details)
        total_reps = sum(item["total_reps"] for item in details)
        total_sets = sum(len(item["sets"]) for item in details)

        avg_intensity = None
        if total_reps:
            avg_intensity = total_volume / total_reps

        load_metrics = calculate_workout_load_metrics(
            workout_exercises=details,
            session_rpe=workout["session_rpe"],
            as_of_created_at=workout["created_at"],
            as_of_workout_id=current_workout_id,
            best_e1rm_by_exercise=e1rm_baselines_by_workout.get(
                current_workout_id,
                {},
            ),
        )

        workout_items.append(
            {
                "id": current_workout_id,
                "date": workout["created_at"][:10],
                "created_at": workout["created_at"],
                "total_volume": total_volume,
                "total_reps": total_reps,
                "total_sets": total_sets,
                "avg_intensity": avg_intensity,
                "session_rpe": workout["session_rpe"],
                "lower_back_pain": workout["lower_back_pain"],
                "load_score": load_metrics["load_score"],
                "load_label": load_metrics["load_label"],
                "compound_score": load_metrics["compound_score"],
                "intensity_score": load_metrics["intensity_score"],
                "back_stress_score": load_metrics["back_stress_score"],
            }
        )

        for item in details:
            exercise_id = int(item["exercise_id"])
            exercise_name = item["exercise_name"]

            if exercise_id not in exercise_stats:
                exercise_stats[exercise_id] = {
                    "exercise_id": exercise_id,
                    "name": exercise_name,
                    "total_volume": 0.0,
                    "total_reps": 0,
                    "total_sets": 0,
                    "best_e1rm": None,
                    "best_set": None,
                }

            stats = exercise_stats[exercise_id]
            stats["total_volume"] += item["total_volume"]
            stats["total_reps"] += item["total_reps"]
            stats["total_sets"] += len(item["sets"])

            for set_row in item["sets"]:
                weight = float(set_row["weight"])
                reps = int(set_row["reps"])
                e1rm = estimated_1rm(weight, reps)

                if e1rm is None:
                    continue

                if stats["best_e1rm"] is None or e1rm > stats["best_e1rm"]:
                    stats["best_e1rm"] = e1rm
                    stats["best_set"] = {
                        "weight": weight,
                        "reps": reps,
                        "workout_id": current_workout_id,
                        "date": workout["created_at"][:10],
                    }

    total_volume = sum(item["total_volume"] for item in workout_items)
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

    return {
        "workouts": workout_items,
        "exercise_stats": sorted(
            exercise_stats.values(),
            key=lambda item: item["total_volume"],
            reverse=True,
        ),
        "summary": {
            "workout_count": len(workout_items),
            "total_volume": total_volume,
            "total_reps": total_reps,
            "total_sets": total_sets,
            "avg_intensity": total_volume / total_reps if total_reps else None,
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
        },
    }
