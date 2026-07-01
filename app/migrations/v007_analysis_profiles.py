import sqlite3
from datetime import datetime, timezone

from app.repositories.analysis_profiles import create_analysis_profiles_table
from app.services.default_analysis_profiles import (
    DEFAULT_LOAD_PROFILE,
    DEFAULT_PROFILE_KEY,
    default_profile_rows,
)


VERSION = 7
NAME = "analysis_profiles"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def label_from_key(profile_key: str) -> str:
    return profile_key.replace("_", " ").replace("-", " ").title()


def seed_default_profiles(conn: sqlite3.Connection) -> None:
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


def import_unknown_exercise_profiles(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT DISTINCT profile_key
        FROM exercises
        WHERE profile_key IS NOT NULL
          AND trim(profile_key) != ''
        ORDER BY profile_key ASC
        """
    ).fetchall()
    now = utc_now()
    max_order = int(
        conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) FROM analysis_profiles"
        ).fetchone()[0]
    )

    for row in rows:
        key = str(row["profile_key"]).strip()
        exists = conn.execute(
            "SELECT 1 FROM analysis_profiles WHERE key = ?",
            (key,),
        ).fetchone()
        if exists is not None:
            continue

        max_order += 10
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
            VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?)
            """,
            (
                key,
                label_from_key(key),
                "imported",
                float(DEFAULT_LOAD_PROFILE["exercise_factor"]),
                float(DEFAULT_LOAD_PROFILE["compound_factor"]),
                float(DEFAULT_LOAD_PROFILE["back_factor"]),
                max_order,
                now,
                now,
            ),
        )


def up(conn: sqlite3.Connection) -> None:
    create_analysis_profiles_table(conn)
    seed_default_profiles(conn)
    import_unknown_exercise_profiles(conn)
    conn.execute(
        "UPDATE analysis_profiles SET is_active = 1 WHERE key = ?",
        (DEFAULT_PROFILE_KEY,),
    )
