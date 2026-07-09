import logging
from datetime import datetime
from threading import RLock
from typing import Any

from app.db import get_db
from app.repositories.exercises import (
    derive_set_metrics,
    get_float_options,
    get_int_options,
    get_option_settings_by_exercise_ids,
    get_weight_options_by_exercise_ids,
    normalize_measurement_settings,
)
from app.repositories import drafts as draft_repository
from app.repositories.workouts import get_previous_set_for_exercise


logger = logging.getLogger("training_log")

DRAFT_LOCK = RLock()


def create_workout_draft() -> dict[str, Any]:
    return {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "session_rpe": None,
        "lower_back_pain": None,
        "workout_exercises": [],
        "next_workout_exercise_id": 1,
        "next_set_id": 1,
    }


def get_active_workout_draft() -> dict[str, Any] | None:
    with DRAFT_LOCK:
        return draft_repository.get_active_draft()


def clear_active_workout_draft() -> None:
    with DRAFT_LOCK:
        draft_repository.clear_active_draft()


def draft_has_logged_sets(draft: dict[str, Any]) -> bool:
    return any(
        bool(item.get("sets"))
        for item in draft.get("workout_exercises", [])
    )


def start_active_workout_draft() -> tuple[dict[str, Any], bool]:
    with DRAFT_LOCK:
        existing_draft = draft_repository.get_active_draft()
        if existing_draft is None:
            started_at = datetime.now().isoformat(timespec="seconds")
            draft = draft_repository.create_active_draft(started_at)
            logger.info(
                "workout.draft.start started_at=%s",
                draft["started_at"],
            )
            return draft, True

        logger.info(
            "workout.draft.start.ignored reason=already_active started_at=%s",
            existing_draft["started_at"],
        )
        return existing_draft, False


def update_active_draft_metadata(updates: dict[str, int | None]) -> bool:
    allowed = {"session_rpe", "lower_back_pain"}
    unexpected = set(updates) - allowed
    if unexpected:
        raise ValueError(f"Unexpected draft metadata fields: {sorted(unexpected)}")

    with DRAFT_LOCK:
        draft = draft_repository.get_active_draft()
        if draft is None:
            logger.warning("workout.draft.metadata.no_active")
            return False

        if not updates:
            return True

        updated = draft_repository.update_active_draft_metadata(updates)

    logger.info(
        "workout.draft.metadata.update updates=%s",
        sorted(updates),
    )
    return updated


def add_exercise_to_active_draft(
    exercise_id: int,
    exercise_name: str,
    profile_key: str | None = None,
) -> dict[str, Any] | None:
    with DRAFT_LOCK:
        draft = draft_repository.get_active_draft()
        if draft is None:
            logger.warning("workout.draft.exercise.add.no_active exercise_id=%s", exercise_id)
            return None

        updated_draft = draft_repository.insert_draft_exercise(exercise_id)
        if updated_draft is None:
            return None

        draft_exercise = updated_draft["workout_exercises"][-1]
        draft_exercise_id = int(draft_exercise["id"])
        position = int(draft_exercise["position"])

    logger.info(
        "workout.draft.exercise.add draft_exercise_id=%s exercise_id=%s position=%s",
        draft_exercise_id,
        exercise_id,
        position,
    )
    return draft_exercise


def add_set_to_active_draft(
    draft_exercise_id: int,
    weight: float,
    reps: int,
) -> dict[str, Any] | None:
    with DRAFT_LOCK:
        draft = draft_repository.get_active_draft()
        if draft is None:
            logger.warning("workout.draft.set.add.no_active draft_exercise_id=%s", draft_exercise_id)
            return None

        draft_exercise = get_draft_workout_exercise(draft, draft_exercise_id)
        if not draft_exercise:
            logger.warning("workout.draft.set.add.exercise_not_found draft_exercise_id=%s", draft_exercise_id)
            return None

        updated_draft = draft_repository.insert_draft_set(
            draft_exercise_id,
            weight=weight,
            reps=reps,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        if updated_draft is None:
            return None

        found = get_draft_set(updated_draft, int(updated_draft["next_set_id"]) - 1)
        if found is None:
            return None
        _, set_entry = found
        set_id = int(set_entry["id"])
        set_number = int(set_entry["set_number"])

    logger.info(
        "workout.draft.set.add set_id=%s draft_exercise_id=%s set_number=%s weight=%s reps=%s",
        set_id,
        draft_exercise_id,
        set_number,
        weight,
        reps,
    )
    return set_entry


def duplicate_active_draft_set(draft_exercise_id: int) -> dict[str, Any] | None:
    with DRAFT_LOCK:
        draft = draft_repository.get_active_draft()
        if draft is None:
            logger.warning("workout.draft.set.duplicate.no_active draft_exercise_id=%s", draft_exercise_id)
            return None

        draft_exercise = get_draft_workout_exercise(draft, draft_exercise_id)
        if not draft_exercise:
            logger.warning("workout.draft.set.duplicate.exercise_not_found draft_exercise_id=%s", draft_exercise_id)
            return None

        if draft_exercise["sets"]:
            source_set = draft_exercise["sets"][-1]
            weight = float(source_set["weight"])
            reps = int(source_set["reps"])
        else:
            previous_set = get_previous_set_for_exercise(
                exercise_id=int(draft_exercise["exercise_id"]),
                current_workout_id=0,
            )
            if not previous_set:
                logger.warning("workout.draft.set.duplicate.no_source draft_exercise_id=%s", draft_exercise_id)
                return None

            weight = float(previous_set["weight"])
            reps = int(previous_set["reps"])

        updated_draft = draft_repository.insert_draft_set(
            draft_exercise_id,
            weight=weight,
            reps=reps,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        if updated_draft is None:
            return None

        found = get_draft_set(updated_draft, int(updated_draft["next_set_id"]) - 1)
        if found is None:
            return None
        _, set_entry = found
        set_id = int(set_entry["id"])
        set_number = int(set_entry["set_number"])

    logger.info(
        "workout.draft.set.duplicate set_id=%s draft_exercise_id=%s set_number=%s weight=%s reps=%s",
        set_id,
        draft_exercise_id,
        set_number,
        weight,
        reps,
    )
    return set_entry


def update_active_draft_set(
    draft_set_id: int,
    weight: float | None = None,
    reps: int | None = None,
) -> dict[str, Any] | None:
    with DRAFT_LOCK:
        draft = draft_repository.get_active_draft()
        if draft is None:
            logger.warning("workout.draft.set.update.no_active set_id=%s", draft_set_id)
            return None

        found = get_draft_set(draft, draft_set_id)
        if not found:
            logger.warning("workout.draft.set.update.not_found set_id=%s", draft_set_id)
            return None

        if not draft_repository.update_draft_set(
            draft_set_id,
            weight=weight,
            reps=reps,
        ):
            return None

        updated_draft = draft_repository.get_active_draft()
        if updated_draft is None:
            return None
        updated_found = get_draft_set(updated_draft, draft_set_id)
        if updated_found is None:
            return None
        _, set_entry = updated_found

    logger.info(
        "workout.draft.set.update set_id=%s weight=%s reps=%s",
        draft_set_id,
        weight,
        reps,
    )
    return set_entry


def delete_active_draft_set(draft_set_id: int) -> bool:
    with DRAFT_LOCK:
        draft = draft_repository.get_active_draft()
        if draft is None:
            logger.warning("workout.draft.set.delete.no_active set_id=%s", draft_set_id)
            return False

        found = get_draft_set(draft, draft_set_id)
        if not found:
            logger.warning("workout.draft.set.delete.not_found set_id=%s", draft_set_id)
            return False

        deleted = draft_repository.delete_draft_set(draft_set_id)

    logger.info("workout.draft.set.delete set_id=%s", draft_set_id)
    return deleted


def delete_active_draft_exercise(draft_exercise_id: int) -> bool:
    with DRAFT_LOCK:
        draft = draft_repository.get_active_draft()
        if draft is None:
            logger.warning("workout.draft.exercise.delete.no_active draft_exercise_id=%s", draft_exercise_id)
            return False

        deleted = draft_repository.delete_draft_exercise(draft_exercise_id)

    logger.info(
        "workout.draft.exercise.delete draft_exercise_id=%s deleted=%s",
        draft_exercise_id,
        deleted,
    )
    return deleted


def finish_active_workout() -> int | None:
    with DRAFT_LOCK:
        active_draft = draft_repository.get_active_draft()
        if active_draft is None:
            logger.warning("workout.draft.finish.no_active")
            return None

        if not draft_has_logged_sets(active_draft):
            logger.warning("workout.draft.finish.empty_blocked")
            return None

        try:
            workout_id = draft_repository.finalize_active_draft()
        except draft_repository.NoActiveDraftError:
            logger.warning("workout.draft.finish.no_active")
            return None
        except draft_repository.EmptyDraftError:
            logger.warning("workout.draft.finish.empty")
            raise

    logger.info("workout.draft.finish workout_id=%s", workout_id)
    return workout_id


def get_draft_workout_exercise(
    draft: dict[str, Any],
    draft_exercise_id: int,
) -> dict[str, Any] | None:
    for item in draft["workout_exercises"]:
        if int(item["id"]) == draft_exercise_id:
            return item

    return None


def get_draft_set(
    draft: dict[str, Any],
    draft_set_id: int,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    for item in draft["workout_exercises"]:
        for set_entry in item["sets"]:
            if int(set_entry["id"]) == draft_set_id:
                return item, set_entry

    return None


def renumber_draft_sets(draft_exercise: dict[str, Any]) -> None:
    for index, set_entry in enumerate(draft_exercise["sets"], start=1):
        set_entry["set_number"] = index


def get_draft_workout_details(draft: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    weights_by_exercise = get_weight_options_by_exercise_ids(
        [
            int(item["exercise_id"])
            for item in draft["workout_exercises"]
        ]
    )
    settings_by_exercise = get_option_settings_by_exercise_ids(
        [
            int(item["exercise_id"])
            for item in draft["workout_exercises"]
        ]
    )
    for item in sorted(draft["workout_exercises"], key=lambda x: (x["position"], x["id"])):
        sets = item["sets"]
        total_volume = sum(float(s["weight"]) * int(s["reps"]) for s in sets)
        total_reps = sum(int(s["reps"]) for s in sets)
        measurement = normalize_measurement_settings(
            measurement_type=item.get("measurement_type"),
            reps_unit=item.get("reps_unit"),
            exercise_name=str(item.get("exercise_name", "")),
        )
        derived_metrics = derive_set_metrics(
            sets,
            measurement["measurement_type"],
        )

        if sets:
            last_set = sets[-1]
            default_weight = float(last_set["weight"])
            default_reps = int(last_set["reps"])
        else:
            previous_set = get_previous_set_for_exercise(
                exercise_id=int(item["exercise_id"]),
                current_workout_id=0,
            )

            if previous_set:
                default_weight = float(previous_set["weight"])
                default_reps = int(previous_set["reps"])
            else:
                settings = settings_by_exercise.get(int(item["exercise_id"]), {})
                default_weight = float(settings.get("default_weight", 0))
                default_reps = int(settings.get("default_reps", 10))

        settings = settings_by_exercise.get(int(item["exercise_id"]), {})
        configured_weights = weights_by_exercise.get(
            int(item["exercise_id"]),
            [],
        )
        set_weights = [float(set_entry["weight"]) for set_entry in sets]
        set_reps = [int(set_entry["reps"]) for set_entry in sets]

        result.append(
            {
                "workout_exercise_id": item["id"],
                "exercise_id": item["exercise_id"],
                "exercise_name": item["exercise_name"],
                "profile_key": item.get("profile_key") or "accessory",
                "measurement_type": measurement["measurement_type"],
                "reps_unit": measurement["reps_unit"],
                "position": item["position"],
                "sets": sets,
                "total_volume": total_volume,
                "total_volume_kg": derived_metrics["total_volume_kg"],
                "bodyweight_reps": derived_metrics["bodyweight_reps"],
                "duration_seconds": derived_metrics["duration_seconds"],
                "distance_m": derived_metrics["distance_m"],
                "total_reps": total_reps,
                "default_weight": default_weight,
                "default_reps": default_reps,
                "configured_weights": configured_weights,
                "weight_options": get_float_options(
                    min_value=float(settings.get("min_weight", 0)),
                    max_value=float(settings.get("max_weight", 200)),
                    step=float(settings.get("weight_step", 2.5)),
                    extra_values=[
                        *configured_weights,
                        *set_weights,
                        default_weight,
                    ],
                ),
                "reps_options": get_int_options(
                    min_value=int(settings.get("min_reps", 1)),
                    max_value=int(settings.get("max_reps", 50)),
                    step=int(settings.get("reps_step", 1)),
                    extra_values=[
                        *set_reps,
                        default_reps,
                    ],
                ),
            }
        )

    return result


def calculate_draft_elapsed_seconds(draft: dict[str, Any]) -> int:
    try:
        started_at = datetime.fromisoformat(draft["started_at"])
    except (KeyError, TypeError, ValueError):
        return 0

    return max(0, int((datetime.now() - started_at).total_seconds()))


def save_workout_draft_to_db(draft: dict[str, Any]) -> int:
    started_at_raw = str(draft["started_at"])
    finished_at = datetime.now().isoformat(timespec="seconds")

    try:
        started_at_dt = datetime.fromisoformat(started_at_raw)
        finished_at_dt = datetime.fromisoformat(finished_at)
        duration_seconds = max(0, int((finished_at_dt - started_at_dt).total_seconds()))
    except ValueError:
        duration_seconds = None

    with get_db() as conn:
        workout_cursor = conn.execute(
            """
            INSERT INTO workouts (
                workout_date,
                created_at,
                finished_at,
                session_rpe,
                lower_back_pain,
                duration_seconds
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                started_at_raw[:10],
                started_at_raw,
                finished_at,
                draft.get("session_rpe"),
                draft.get("lower_back_pain"),
                duration_seconds,
            ),
        )

        workout_id = int(workout_cursor.lastrowid)

        for draft_exercise in sorted(
            draft["workout_exercises"],
            key=lambda item: (item["position"], item["id"]),
        ):
            workout_exercise_cursor = conn.execute(
                """
                INSERT INTO workout_exercises (
                    workout_id,
                    exercise_id,
                    position,
                    measurement_type,
                    reps_unit
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    workout_id,
                    int(draft_exercise["exercise_id"]),
                    int(draft_exercise["position"]),
                    draft_exercise.get("measurement_type") or "weighted_reps",
                    draft_exercise.get("reps_unit") or "reps",
                ),
            )

            workout_exercise_id = int(workout_exercise_cursor.lastrowid)

            for set_entry in draft_exercise["sets"]:
                conn.execute(
                    """
                    INSERT INTO set_entries
                        (workout_exercise_id, set_number, weight, reps, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        workout_exercise_id,
                        int(set_entry["set_number"]),
                        float(set_entry["weight"]),
                        int(set_entry["reps"]),
                        str(set_entry["created_at"]),
                    ),
                )

    logger.info(
        "workout.draft.save workout_id=%s exercises=%s duration_seconds=%s",
        workout_id,
        len(draft["workout_exercises"]),
        duration_seconds,
    )

    return workout_id
