import logging
from datetime import datetime
from threading import RLock
from typing import Any

from app.db import get_db
from app.repositories import drafts as draft_repository
from app.repositories.workouts import get_previous_set_for_exercise


logger = logging.getLogger("training_log")

ACTIVE_WORKOUT_DRAFT: dict[str, Any] | None = None
DRAFT_LOCK = RLock()


def _get_active_workout_draft_locked() -> dict[str, Any] | None:
    global ACTIVE_WORKOUT_DRAFT

    if ACTIVE_WORKOUT_DRAFT is None:
        ACTIVE_WORKOUT_DRAFT = draft_repository.get_active_draft()

    return ACTIVE_WORKOUT_DRAFT


def create_workout_draft() -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")

    return {
        "started_at": now,
        "session_rpe": None,
        "lower_back_pain": None,
        "workout_exercises": [],
        "next_workout_exercise_id": 1,
        "next_set_id": 1,
    }


def get_active_workout_draft() -> dict[str, Any] | None:
    with DRAFT_LOCK:
        return _get_active_workout_draft_locked()


def clear_active_workout_draft() -> None:
    global ACTIVE_WORKOUT_DRAFT

    with DRAFT_LOCK:
        ACTIVE_WORKOUT_DRAFT = None
        draft_repository.clear_active_draft()


def start_active_workout_draft() -> tuple[dict[str, Any], bool]:
    global ACTIVE_WORKOUT_DRAFT

    with DRAFT_LOCK:
        existing_draft = _get_active_workout_draft_locked()
        if existing_draft is None:
            ACTIVE_WORKOUT_DRAFT = create_workout_draft()
            draft_repository.replace_active_draft(ACTIVE_WORKOUT_DRAFT)
            logger.info(
                "workout.draft.start started_at=%s",
                ACTIVE_WORKOUT_DRAFT["started_at"],
            )
            return ACTIVE_WORKOUT_DRAFT, True

        logger.info(
            "workout.draft.start.ignored reason=already_active started_at=%s",
            existing_draft["started_at"],
        )
        return existing_draft, False


def update_active_draft_metadata(
    session_rpe: int | None,
    lower_back_pain: int | None,
) -> bool:
    with DRAFT_LOCK:
        draft = _get_active_workout_draft_locked()
        if draft is None:
            logger.warning("workout.draft.metadata.no_active")
            return False

        draft["session_rpe"] = session_rpe
        draft["lower_back_pain"] = lower_back_pain
        draft_repository.replace_active_draft(draft)

    logger.info(
        "workout.draft.metadata.update session_rpe=%s lower_back_pain=%s",
        session_rpe,
        lower_back_pain,
    )
    return True


def add_exercise_to_active_draft(
    exercise_id: int,
    exercise_name: str,
) -> dict[str, Any] | None:
    with DRAFT_LOCK:
        draft = _get_active_workout_draft_locked()
        if draft is None:
            logger.warning("workout.draft.exercise.add.no_active exercise_id=%s", exercise_id)
            return None

        draft_exercise_id = int(draft["next_workout_exercise_id"])
        draft["next_workout_exercise_id"] = draft_exercise_id + 1
        position = len(draft["workout_exercises"]) + 1

        draft_exercise = {
            "id": draft_exercise_id,
            "exercise_id": exercise_id,
            "exercise_name": exercise_name,
            "position": position,
            "sets": [],
        }
        draft["workout_exercises"].append(draft_exercise)
        draft_repository.replace_active_draft(draft)

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
        draft = _get_active_workout_draft_locked()
        if draft is None:
            logger.warning("workout.draft.set.add.no_active draft_exercise_id=%s", draft_exercise_id)
            return None

        draft_exercise = get_draft_workout_exercise(draft, draft_exercise_id)
        if not draft_exercise:
            logger.warning("workout.draft.set.add.exercise_not_found draft_exercise_id=%s", draft_exercise_id)
            return None

        set_id = int(draft["next_set_id"])
        draft["next_set_id"] = set_id + 1
        set_number = len(draft_exercise["sets"]) + 1

        set_entry = {
            "id": set_id,
            "set_number": set_number,
            "weight": weight,
            "reps": reps,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        draft_exercise["sets"].append(set_entry)
        draft_repository.replace_active_draft(draft)

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
        draft = _get_active_workout_draft_locked()
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

        set_id = int(draft["next_set_id"])
        draft["next_set_id"] = set_id + 1
        set_number = len(draft_exercise["sets"]) + 1

        set_entry = {
            "id": set_id,
            "set_number": set_number,
            "weight": weight,
            "reps": reps,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        draft_exercise["sets"].append(set_entry)
        draft_repository.replace_active_draft(draft)

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
        draft = _get_active_workout_draft_locked()
        if draft is None:
            logger.warning("workout.draft.set.update.no_active set_id=%s", draft_set_id)
            return None

        found = get_draft_set(draft, draft_set_id)
        if not found:
            logger.warning("workout.draft.set.update.not_found set_id=%s", draft_set_id)
            return None

        _, set_entry = found

        if weight is not None:
            set_entry["weight"] = weight

        if reps is not None:
            set_entry["reps"] = reps

        draft_repository.replace_active_draft(draft)

    logger.info(
        "workout.draft.set.update set_id=%s weight=%s reps=%s",
        draft_set_id,
        weight,
        reps,
    )
    return set_entry


def delete_active_draft_set(draft_set_id: int) -> bool:
    with DRAFT_LOCK:
        draft = _get_active_workout_draft_locked()
        if draft is None:
            logger.warning("workout.draft.set.delete.no_active set_id=%s", draft_set_id)
            return False

        found = get_draft_set(draft, draft_set_id)
        if not found:
            logger.warning("workout.draft.set.delete.not_found set_id=%s", draft_set_id)
            return False

        draft_exercise, _ = found
        draft_exercise["sets"] = [
            set_entry for set_entry in draft_exercise["sets"]
            if int(set_entry["id"]) != draft_set_id
        ]
        renumber_draft_sets(draft_exercise)
        draft_repository.replace_active_draft(draft)

    logger.info("workout.draft.set.delete set_id=%s", draft_set_id)
    return True


def delete_active_draft_exercise(draft_exercise_id: int) -> bool:
    with DRAFT_LOCK:
        draft = _get_active_workout_draft_locked()
        if draft is None:
            logger.warning("workout.draft.exercise.delete.no_active draft_exercise_id=%s", draft_exercise_id)
            return False

        before_count = len(draft["workout_exercises"])
        draft["workout_exercises"] = [
            item for item in draft["workout_exercises"]
            if int(item["id"]) != draft_exercise_id
        ]

        for index, item in enumerate(draft["workout_exercises"], start=1):
            item["position"] = index

        deleted = before_count != len(draft["workout_exercises"])
        draft_repository.replace_active_draft(draft)

    logger.info(
        "workout.draft.exercise.delete draft_exercise_id=%s deleted=%s",
        draft_exercise_id,
        deleted,
    )
    return deleted


def finish_active_workout() -> int | None:
    global ACTIVE_WORKOUT_DRAFT

    with DRAFT_LOCK:
        if _get_active_workout_draft_locked() is None:
            logger.warning("workout.draft.finish.no_active")
            return None

        try:
            workout_id = draft_repository.finalize_active_draft()
        except draft_repository.NoActiveDraftError:
            ACTIVE_WORKOUT_DRAFT = None
            logger.warning("workout.draft.finish.no_active")
            return None
        except draft_repository.EmptyDraftError:
            logger.warning("workout.draft.finish.empty")
            raise

        ACTIVE_WORKOUT_DRAFT = None

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

    for item in sorted(draft["workout_exercises"], key=lambda x: (x["position"], x["id"])):
        sets = item["sets"]
        total_volume = sum(float(s["weight"]) * int(s["reps"]) for s in sets)
        total_reps = sum(int(s["reps"]) for s in sets)

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
                default_weight = 0.0
                default_reps = 10

        result.append(
            {
                "workout_exercise_id": item["id"],
                "exercise_id": item["exercise_id"],
                "exercise_name": item["exercise_name"],
                "position": item["position"],
                "sets": sets,
                "total_volume": total_volume,
                "total_reps": total_reps,
                "default_weight": default_weight,
                "default_reps": default_reps,
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
                INSERT INTO workout_exercises (workout_id, exercise_id, position)
                VALUES (?, ?, ?)
                """,
                (
                    workout_id,
                    int(draft_exercise["exercise_id"]),
                    int(draft_exercise["position"]),
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
