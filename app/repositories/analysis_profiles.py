import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.services.default_analysis_profiles import (
    DEFAULT_LOAD_PROFILE,
    DEFAULT_LOAD_PROFILES_BY_KEY,
    DEFAULT_PROFILE_KEY,
    default_profile_rows,
)


PROFILE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
MAX_FACTOR = 5.0


class DuplicateProfileKeyError(ValueError):
    pass


class DuplicateProfileLabelError(ValueError):
    pass


class ProfileInUseError(ValueError):
    pass


class InvalidProfileKeyError(ValueError):
    pass


class AccessoryProfileError(ValueError):
    pass


class BuiltInProfileDeleteError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_profile_key(value: str) -> str:
    key = str(value or "").strip().lower()
    if not key or not PROFILE_KEY_RE.match(key):
        raise InvalidProfileKeyError(
            "Profile key must use lowercase letters, numbers, dashes, or underscores."
        )
    return key


def slugify_profile_key(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return slug or "profile"


def validate_profile_text(value: str, field_name: str, *, max_length: int = 120) -> str:
    normalized = " ".join(str(value or "").strip().split())
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} is too long.")
    return normalized


def validate_factor(value: float, field_name: str) -> float:
    factor = float(value)
    if factor < 0 or factor > MAX_FACTOR:
        raise ValueError(f"{field_name} must be between 0 and {MAX_FACTOR:g}.")
    return factor


def create_analysis_profiles_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS analysis_profiles (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            category TEXT NOT NULL,
            exercise_factor REAL NOT NULL CHECK (exercise_factor >= 0),
            compound_factor REAL NOT NULL CHECK (compound_factor >= 0),
            back_factor REAL NOT NULL CHECK (back_factor >= 0),
            is_builtin INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0, 1)),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_profiles_label_nocase
        ON analysis_profiles(label COLLATE NOCASE);

        CREATE INDEX IF NOT EXISTS idx_analysis_profiles_active_order
        ON analysis_profiles(is_active, sort_order, label);
        """
    )


def ensure_default_analysis_profiles(conn: sqlite3.Connection) -> None:
    create_analysis_profiles_table(conn)
    now = utc_now()
    for row in default_profile_rows():
        conn.execute(
            """
            INSERT INTO analysis_profiles (
                key,
                label,
                category,
                exercise_factor,
                compound_factor,
                back_factor,
                is_builtin,
                is_active,
                sort_order,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO NOTHING
            """,
            (
                row["key"],
                row["label"],
                row["category"],
                row["exercise_factor"],
                row["compound_factor"],
                row["back_factor"],
                1 if row["is_builtin"] else 0,
                1 if row["is_active"] else 0,
                row["sort_order"],
                now,
                now,
            ),
        )

    conn.execute(
        """
        UPDATE analysis_profiles
        SET is_active = 1,
            updated_at = ?
        WHERE key = ?
          AND is_active = 0
        """,
        (now, DEFAULT_PROFILE_KEY),
    )


def exercise_counts_by_profile(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT profile_key, COUNT(*) AS exercise_count
        FROM exercises
        GROUP BY profile_key
        """
    ).fetchall()
    return {
        str(row["profile_key"] or DEFAULT_PROFILE_KEY): int(row["exercise_count"])
        for row in rows
    }


def row_to_profile(row: sqlite3.Row, exercise_count: int = 0) -> dict[str, Any]:
    return {
        "key": str(row["key"]),
        "label": str(row["label"]),
        "category": str(row["category"]),
        "exercise_factor": float(row["exercise_factor"]),
        "compound_factor": float(row["compound_factor"]),
        "back_factor": float(row["back_factor"]),
        "is_builtin": bool(row["is_builtin"]),
        "is_active": bool(row["is_active"]),
        "sort_order": int(row["sort_order"]),
        "exercise_count": exercise_count,
    }


def list_analysis_profiles(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    counts = exercise_counts_by_profile(conn)
    rows = conn.execute(
        """
        SELECT *
        FROM analysis_profiles
        ORDER BY is_active DESC, sort_order ASC, label COLLATE NOCASE ASC, key ASC
        """
    ).fetchall()
    return [row_to_profile(row, counts.get(str(row["key"]), 0)) for row in rows]


def get_analysis_profile(
    conn: sqlite3.Connection,
    profile_key: str,
) -> dict[str, Any] | None:
    key = str(profile_key or "").strip()
    row = conn.execute(
        "SELECT * FROM analysis_profiles WHERE key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return None
    return row_to_profile(row, exercise_counts_by_profile(conn).get(key, 0))


def profile_exists(conn: sqlite3.Connection, profile_key: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM analysis_profiles WHERE key = ?",
        (profile_key,),
    ).fetchone()
    return row is not None


def active_profile_exists(conn: sqlite3.Connection, profile_key: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM analysis_profiles
        WHERE key = ?
          AND is_active = 1
        """,
        (profile_key,),
    ).fetchone()
    return row is not None


def load_profiles_by_key(conn: sqlite3.Connection) -> dict[str, dict[str, float | str]]:
    rows = conn.execute(
        """
        SELECT key, category, exercise_factor, compound_factor, back_factor
        FROM analysis_profiles
        """
    ).fetchall()
    profiles = {
        str(row["key"]): {
            "category": str(row["category"]),
            "exercise_factor": float(row["exercise_factor"]),
            "compound_factor": float(row["compound_factor"]),
            "back_factor": float(row["back_factor"]),
        }
        for row in rows
    }
    profiles.setdefault(DEFAULT_PROFILE_KEY, DEFAULT_LOAD_PROFILE)
    return profiles


def next_profile_sort_order(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 10 FROM analysis_profiles"
        ).fetchone()[0]
    )


def unique_generated_profile_key(conn: sqlite3.Connection, label: str) -> str:
    base = slugify_profile_key(label)[:80]
    candidate = base
    suffix = 2
    while profile_exists(conn, candidate):
        suffix_text = f"_{suffix}"
        candidate = f"{base[:80 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return candidate


def label_exists(
    conn: sqlite3.Connection,
    label: str,
    *,
    excluding_key: str | None = None,
) -> bool:
    params: list[Any] = [label]
    exclude_sql = ""
    if excluding_key is not None:
        exclude_sql = "AND key != ?"
        params.append(excluding_key)

    row = conn.execute(
        f"""
        SELECT 1
        FROM analysis_profiles
        WHERE label = ? COLLATE NOCASE
          {exclude_sql}
        """,
        params,
    ).fetchone()
    return row is not None


def create_analysis_profile(
    conn: sqlite3.Connection,
    *,
    label: str,
    category: str,
    exercise_factor: float,
    compound_factor: float,
    back_factor: float,
    key: str | None = None,
) -> dict[str, Any]:
    normalized_label = validate_profile_text(label, "Label")
    normalized_category = validate_profile_text(category, "Category")
    normalized_key = (
        normalize_profile_key(key)
        if key is not None and str(key).strip()
        else unique_generated_profile_key(conn, normalized_label)
    )

    if profile_exists(conn, normalized_key):
        raise DuplicateProfileKeyError("Profile key already exists.")
    if label_exists(conn, normalized_label):
        raise DuplicateProfileLabelError("Profile label already exists.")

    now = utc_now()
    conn.execute(
        """
        INSERT INTO analysis_profiles (
            key,
            label,
            category,
            exercise_factor,
            compound_factor,
            back_factor,
            is_builtin,
            is_active,
            sort_order,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 0, 1, ?, ?, ?)
        """,
        (
            normalized_key,
            normalized_label,
            normalized_category,
            validate_factor(exercise_factor, "Exercise factor"),
            validate_factor(compound_factor, "Compound factor"),
            validate_factor(back_factor, "Back factor"),
            next_profile_sort_order(conn),
            now,
            now,
        ),
    )
    profile = get_analysis_profile(conn, normalized_key)
    if profile is None:
        raise RuntimeError("Created profile could not be loaded.")
    return profile


def update_analysis_profile(
    conn: sqlite3.Connection,
    profile_key: str,
    *,
    label: str | None = None,
    category: str | None = None,
    exercise_factor: float | None = None,
    compound_factor: float | None = None,
    back_factor: float | None = None,
    is_active: bool | None = None,
) -> dict[str, Any] | None:
    key = normalize_profile_key(profile_key)
    current = get_analysis_profile(conn, key)
    if current is None:
        return None

    updated_label = current["label"] if label is None else validate_profile_text(label, "Label")
    updated_category = (
        current["category"]
        if category is None
        else validate_profile_text(category, "Category")
    )
    updated_exercise_factor = (
        current["exercise_factor"]
        if exercise_factor is None
        else validate_factor(exercise_factor, "Exercise factor")
    )
    updated_compound_factor = (
        current["compound_factor"]
        if compound_factor is None
        else validate_factor(compound_factor, "Compound factor")
    )
    updated_back_factor = (
        current["back_factor"]
        if back_factor is None
        else validate_factor(back_factor, "Back factor")
    )
    updated_active = current["is_active"] if is_active is None else bool(is_active)

    if key == DEFAULT_PROFILE_KEY and not updated_active:
        raise AccessoryProfileError("Accessory profile must stay active.")
    if not updated_active and current["exercise_count"] > 0:
        raise ProfileInUseError("Profile is used by exercises and cannot be deactivated.")
    if label_exists(conn, updated_label, excluding_key=key):
        raise DuplicateProfileLabelError("Profile label already exists.")

    conn.execute(
        """
        UPDATE analysis_profiles
        SET label = ?,
            category = ?,
            exercise_factor = ?,
            compound_factor = ?,
            back_factor = ?,
            is_active = ?,
            updated_at = ?
        WHERE key = ?
        """,
        (
            updated_label,
            updated_category,
            updated_exercise_factor,
            updated_compound_factor,
            updated_back_factor,
            1 if updated_active else 0,
            utc_now(),
            key,
        ),
    )
    return get_analysis_profile(conn, key)


def delete_analysis_profile(
    conn: sqlite3.Connection,
    profile_key: str,
) -> dict[str, Any] | None:
    key = normalize_profile_key(profile_key)
    profile = get_analysis_profile(conn, key)
    if profile is None:
        return None

    if key == DEFAULT_PROFILE_KEY:
        raise AccessoryProfileError("Accessory profile cannot be deleted.")
    if profile["is_builtin"]:
        raise BuiltInProfileDeleteError("Built-in analysis types cannot be deleted.")
    if profile["exercise_count"] > 0:
        raise ProfileInUseError(
            "Profile is used by exercises and cannot be deleted."
        )

    conn.execute(
        "DELETE FROM analysis_profiles WHERE key = ?",
        (key,),
    )
    return profile


def backup_profile_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            key,
            label,
            category,
            exercise_factor,
            compound_factor,
            back_factor,
            is_builtin,
            is_active,
            sort_order
        FROM analysis_profiles
        ORDER BY sort_order ASC, label COLLATE NOCASE ASC, key ASC
        """
    ).fetchall()
    return [
        {
            "key": str(row["key"]),
            "label": str(row["label"]),
            "category": str(row["category"]),
            "exercise_factor": float(row["exercise_factor"]),
            "compound_factor": float(row["compound_factor"]),
            "back_factor": float(row["back_factor"]),
            "is_builtin": int(row["is_builtin"]),
            "is_active": int(row["is_active"]),
            "sort_order": int(row["sort_order"]),
        }
        for row in rows
    ]
