# Codex Handoff: Training Log

## 0. Current Migration Status

As of 2026-06-16, the migration has switched from incremental fallback to a React-only upgrade path:

* React is the only product UI.
* Legacy Jinja routes and templates have been removed.
* FastAPI serves `/api/v1` JSON endpoints and falls back to the bundled React app for non-API paths.
* Docker builds the frontend in a Node stage and copies `frontend/dist` into the Python runtime image.
* Runtime operation must remain fully local/offline: no CDN scripts, hosted fonts, remote images, or online APIs are required for core use.
* Production can continue running the old image until the React-only build is ready to deploy.

## 1. Project Summary

**Repository:** `mykzhu/training_log`
**Primary branch:** `master`

Training Log is a self-hosted, mobile-first strength-training logger intended to run as a Docker container and Home Assistant add-on.

The current application is a FastAPI + SQLite + Jinja2 server-rendered app. It supports:

* Starting and finishing a workout
* Logging exercises, sets, reps, and weight
* Editing completed workouts
* Session RPE and lower-back pain tracking
* Workout duration
* History and workout detail pages
* Backup, restore, and database reset
* Strength and load analysis
* Stats dashboards with custom HTML/CSS charts and sparkbars
* Request and action logging

The next major goal is to migrate the application to a dynamic frontend that can support richer charts, interactive editing, and future analytics without full-page reloads.

---

## 2. Product Requirements

### Core workout logging

The UI must remain optimized for phone use.

Users must be able to:

* Start a workout explicitly
* See a live workout timer
* Add an existing exercise
* Create a new exercise
* Add sets with weight and reps
* Delete sets
* Delete exercises from the active workout
* Record session RPE
* Record lower-back pain
* Finish the workout
* Persist the workout only after Finish is pressed

### Weight selection

Default weight options:

* `0–70 kg` in `1 kg` steps
* `75–150 kg` in `5 kg` steps

Existing non-standard values must remain selectable, including values such as:

* `17.75`
* `20.35`
* `23.45`

The application currently injects stored/default weights into the generated option list.

### Workout metadata

Each completed workout may include:

* Start datetime
* Finish datetime
* Duration
* Session RPE
* Lower-back pain score

RPE and lower-back pain fields are optional.

Empty form values must not be parsed directly as integers. Current form handlers should accept them as strings and convert them explicitly.

### History and editing

Users must be able to:

* View recent workouts
* Open a workout detail page
* Edit workout datetime
* Edit RPE and lower-back pain
* Add or remove exercises
* Add, edit, duplicate, or delete sets
* Delete a workout

### Backup and restore

The application must support:

* JSON export
* JSON import
* Full data reset
* Backward compatibility with backup schema version 1
* Current backup schema version 2

### Analytics

Current analysis includes:

* Total volume
* Total sets and reps
* Average load
* Average weight per rep
* Estimated 1RM
* Relative intensity
* Compound load
* Back-stress score
* Session RPE trend
* Lower-back pain trend
* Recovery context
* Progress/repeat/deload/recovery recommendations
* Per-exercise analysis
* PR detection

Future analytics should support interactive charts, filtering, drill-down, and comparisons.

---

## 3. Current Technology Stack

### Backend

* Python 3.12
* FastAPI
* Uvicorn
* SQLite
* Jinja2
* `python-multipart`

### Frontend

Current frontend:

* Server-rendered Jinja templates
* Inline CSS
* Inline JavaScript
* HTML forms with redirects
* Custom CSS charts and Unicode sparkbars

Planned frontend:

* React
* TypeScript
* Vite
* Recharts
* Same-origin FastAPI JSON API

### Deployment

* Docker
* Persistent SQLite database under `/data`
* Home Assistant add-on support
* `DB_PATH` configurable through environment variables
* Default port `8000`

---

## 4. Current Architecture

The current application is mostly contained in one large file:

```text
app/
  main.py
  templates/
    index.html
    history.html
    workout.html
    edit_workout.html
    edit_set.html
    backup.html
    stats.html
    stats2.html
```

`app/main.py` currently contains:

* Database setup
* Lightweight migrations
* Backup validation and restore
* Draft workout state
* Workout CRUD
* Exercise CRUD
* Set CRUD
* Analysis formulas
* Recovery calculations
* Recommendation logic
* Stats aggregation
* HTML page routes
* Form routes
* Jinja filters
* Logging middleware

This monolithic structure is now the main technical limitation.

---

## 5. Target Architecture

Refactor the backend before replacing the UI.

```text
app/
  main.py
  config.py
  db.py
  migrations.py
  schemas.py

  repositories/
    exercises.py
    workouts.py
    drafts.py
    stats.py

  services/
    workout_service.py
    draft_service.py
    analysis_service.py
    stats_service.py
    backup_service.py

  routes/
    pages.py
    api_workouts.py
    api_stats.py
    api_backup.py

  templates/
    ...legacy Jinja templates...

frontend/
  package.json
  vite.config.ts
  tsconfig.json

  src/
    main.tsx
    App.tsx

    api/
      client.ts
      workouts.ts
      stats.ts
      backup.ts

    components/
      StatCard.tsx
      StatusBadge.tsx
      ExerciseCard.tsx
      SetRow.tsx
      WorkoutTimer.tsx

    pages/
      CurrentWorkoutPage.tsx
      HistoryPage.tsx
      WorkoutPage.tsx
      EditWorkoutPage.tsx
      StatsPage.tsx
      BackupPage.tsx
```

### Architecture rules

* React and JSON API must use the same service layer.
* Analysis formulas must not be duplicated in route handlers or frontend code.
* React owns all product page routes; no legacy Jinja fallback remains.
* The frontend must not calculate authoritative training metrics.
* FastAPI remains the source of truth.
* API endpoints should be versioned under `/api/v1`.
* The built frontend should eventually be served by FastAPI from the same origin.
* The app must work without internet access after installation. Runtime behavior must not depend on CDNs, remote fonts, remote scripts, hosted images, or online API services.

---

## 6. Important Decisions

### Dynamic UI

Use React + TypeScript + Vite.

Reason:

* Current forms reload the full page after every action.
* The workout timer, set editing, and metadata updates benefit from local state.
* Stats require real chart components and interactive filters.
* Recharts is suitable for the planned dashboards.

HTMX is not the preferred direction because the project is moving toward a full interactive dashboard rather than isolated partial-page updates.

### Incremental migration

Do not replace the whole UI at once.

Migration order:

1. Stabilize backend logic
2. Add tests
3. Split `main.py`
4. Make draft persistence reliable
5. Add JSON API
6. Build React Current Workout page
7. Build React Stats page
8. Migrate History and Workout Detail
9. Migrate editing and backup
10. Remove legacy Jinja only after parity

### Draft workout behavior

A workout must not appear in workout history until the user presses Finish.

Current behavior:

* Active workout exists as a Python in-memory dictionary.
* Completed workout is written to SQLite on Finish.

Required future behavior:

* Draft survives container restart.
* Draft still remains separate from completed workouts.
* The `workouts` table should contain completed workouts only.

Preferred persistence options:

1. Dedicated SQLite draft tables
2. A single atomic JSON draft file under `/data`

SQLite draft tables are preferred for consistency and future API use.

### Home Assistant path prefix

Do not add an application base-path prefix yet.

Current routes remain rooted at:

```text
/
/history
/stats
/backup
/workouts/...
```

Home Assistant ingress/base-prefix support is deferred.

Frontend code should nevertheless avoid scattering hardcoded absolute URLs. API URL construction should be centralized.

### Stats pages

`/stats` and `/stats2` currently overlap.

Long-term decision:

* Keep one canonical Stats data model
* Keep one final Stats UI
* Treat `/stats2` as temporary experimentation
* Do not maintain separate formulas for each page

### Exercise load profiles

Current exercise analysis derives profiles from normalized exercise names.

Example:

```python
EXERCISE_LOAD_PROFILES = {
    "deadlift": {
        "category": "heavy compound",
        "exercise_factor": 1.8,
        "compound_factor": 1.8,
        "back_factor": 1.8,
    },
}
```

This is acceptable for the current prototype but should move to exercise metadata in the database.

---

## 7. Current Database Schema

### `exercises`

```sql
CREATE TABLE exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
```

### `workouts`

```sql
CREATE TABLE workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    session_rpe INTEGER,
    lower_back_pain INTEGER,
    duration_seconds INTEGER
);
```

### `workout_exercises`

```sql
CREATE TABLE workout_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER NOT NULL,
    exercise_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    FOREIGN KEY (workout_id)
        REFERENCES workouts(id)
        ON DELETE CASCADE,
    FOREIGN KEY (exercise_id)
        REFERENCES exercises(id)
        ON DELETE CASCADE
);
```

### `set_entries`

```sql
CREATE TABLE set_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_exercise_id INTEGER NOT NULL,
    set_number INTEGER NOT NULL,
    weight REAL NOT NULL DEFAULT 0,
    reps INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workout_exercise_id)
        REFERENCES workout_exercises(id)
        ON DELETE CASCADE
);
```

### Proposed exercise metadata

Potential future columns:

```sql
ALTER TABLE exercises ADD COLUMN category TEXT;
ALTER TABLE exercises ADD COLUMN exercise_factor REAL;
ALTER TABLE exercises ADD COLUMN compound_factor REAL;
ALTER TABLE exercises ADD COLUMN back_factor REAL;
```

A more flexible alternative is a separate `exercise_profiles` table.

### Proposed persistent draft schema

Suggested structure:

```sql
CREATE TABLE active_workout_draft (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    started_at TEXT NOT NULL,
    session_rpe INTEGER,
    lower_back_pain INTEGER,
    next_workout_exercise_id INTEGER NOT NULL,
    next_set_id INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE active_draft_exercises (
    id INTEGER PRIMARY KEY,
    exercise_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    FOREIGN KEY (exercise_id)
        REFERENCES exercises(id)
);

CREATE TABLE active_draft_sets (
    id INTEGER PRIMARY KEY,
    draft_exercise_id INTEGER NOT NULL,
    set_number INTEGER NOT NULL,
    weight REAL NOT NULL,
    reps INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (draft_exercise_id)
        REFERENCES active_draft_exercises(id)
        ON DELETE CASCADE
);
```

Only one active draft is currently required.

---

## 8. Current Draft Representation

The active draft currently resembles:

```python
{
    "started_at": "2026-06-15T10:00:00",
    "session_rpe": None,
    "lower_back_pain": None,
    "workout_exercises": [
        {
            "id": 1,
            "exercise_id": 4,
            "exercise_name": "DB Row",
            "position": 1,
            "sets": [
                {
                    "id": 1,
                    "set_number": 1,
                    "weight": 14.25,
                    "reps": 12,
                    "created_at": "2026-06-15T10:05:00",
                }
            ],
        }
    ],
    "next_workout_exercise_id": 2,
    "next_set_id": 2,
}
```

Current storage:

```python
ACTIVE_WORKOUT_DRAFT: dict[str, Any] | None = None
DRAFT_LOCK = RLock()
```

This must be replaced before multi-worker deployment or reliable restart recovery.

---

## 9. Current Important Routes

### Pages

```text
GET  /
GET  /history
GET  /workouts/{workout_id}
GET  /workouts/{workout_id}/edit
GET  /stats
GET  /stats2
GET  /backup
```

### Active workout forms

```text
POST /workouts/start
POST /draft/metadata
POST /draft/exercise
POST /draft-exercises/{draft_exercise_id}/sets
POST /draft-exercises/{draft_exercise_id}/sets/duplicate
POST /draft-sets/{draft_set_id}/delete
POST /draft-exercises/{draft_exercise_id}/delete
POST /workouts/finish
```

### Completed workout editing

```text
POST /workouts/{workout_id}/update
POST /workouts/{workout_id}/delete
POST /workouts/{workout_id}/exercise
POST /workout-exercises/{workout_exercise_id}/sets
POST /workout-exercises/{workout_exercise_id}/sets/duplicate
POST /workout-exercises/{workout_exercise_id}/delete
POST /sets/{set_id}/delete
```

### Backup

```text
GET  /backup/export.json
POST /backup/import
POST /backup/reset
```

---

## 10. Target JSON API

Use JSON request and response bodies.

### Current workout

```text
GET    /api/v1/current-workout
POST   /api/v1/current-workout/start
PATCH  /api/v1/current-workout/metadata
POST   /api/v1/current-workout/exercises
DELETE /api/v1/current-workout/exercises/{draft_exercise_id}
POST   /api/v1/current-workout/exercises/{draft_exercise_id}/sets
POST   /api/v1/current-workout/exercises/{draft_exercise_id}/sets/duplicate
PATCH  /api/v1/current-workout/sets/{draft_set_id}
DELETE /api/v1/current-workout/sets/{draft_set_id}
POST   /api/v1/current-workout/finish
DELETE /api/v1/current-workout
```

### Exercises

```text
GET   /api/v1/exercises
POST  /api/v1/exercises
PATCH /api/v1/exercises/{exercise_id}
```

### Completed workouts

```text
GET    /api/v1/workouts
GET    /api/v1/workouts/{workout_id}
PATCH  /api/v1/workouts/{workout_id}
DELETE /api/v1/workouts/{workout_id}

POST   /api/v1/workouts/{workout_id}/exercises
DELETE /api/v1/workouts/{workout_id}/exercises/{workout_exercise_id}

POST   /api/v1/workout-exercises/{workout_exercise_id}/sets
PATCH  /api/v1/sets/{set_id}
DELETE /api/v1/sets/{set_id}
```

### Stats

```text
GET /api/v1/stats
GET /api/v1/stats?limit=30
GET /api/v1/stats?limit=all
GET /api/v1/exercises/{exercise_id}/stats
```

### Backup

```text
GET  /api/v1/backup
POST /api/v1/backup/import
POST /api/v1/backup/reset
```

For browser downloads, the existing `/backup/export.json` route may remain.

---

## 11. Suggested API Models

```python
from pydantic import BaseModel, Field


class WorkoutMetadataUpdate(BaseModel):
    session_rpe: int | None = Field(default=None, ge=1, le=10)
    lower_back_pain: int | None = Field(default=None, ge=0, le=10)


class AddExerciseRequest(BaseModel):
    exercise_id: int


class AddSetRequest(BaseModel):
    weight: float = Field(ge=0)
    reps: int = Field(ge=1, le=100)


class UpdateSetRequest(BaseModel):
    weight: float | None = Field(default=None, ge=0)
    reps: int | None = Field(default=None, ge=1, le=100)


class ExerciseSummary(BaseModel):
    draft_exercise_id: int
    exercise_id: int
    exercise_name: str
    position: int
    total_sets: int
    total_reps: int
    total_volume: float


class CurrentWorkoutResponse(BaseModel):
    active: bool
    started_at: str | None
    elapsed_seconds: int
    session_rpe: int | None
    lower_back_pain: int | None
    total_sets: int
    total_reps: int
    total_volume: float
    exercises: list[dict]
```

---

## 12. Current Form Parsing Bug Pattern

HTML selects send an empty string for unselected values:

```html
<option value="">Back Pain</option>
```

FastAPI must not receive this directly as `int | None`.

Incorrect:

```python
def update_draft_metadata(
    session_rpe: int | None = Form(None),
    lower_back_pain: int | None = Form(None),
):
    ...
```

Correct:

```python
def parse_optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None

    return int(value)


def update_draft_metadata(
    session_rpe: str | None = Form(None),
    lower_back_pain: str | None = Form(None),
):
    parsed_session_rpe = parse_optional_int(session_rpe)
    parsed_lower_back_pain = parse_optional_int(lower_back_pain)

    draft["session_rpe"] = parsed_session_rpe
    draft["lower_back_pain"] = parsed_lower_back_pain
```

The JSON API will avoid this specific form-encoding issue.

---

## 13. Current Workout Finish Flow

Current behavior:

```python
@app.post("/workouts/finish")
def finish_workout():
    global ACTIVE_WORKOUT_DRAFT

    with DRAFT_LOCK:
        if ACTIVE_WORKOUT_DRAFT is None:
            return RedirectResponse("/", status_code=303)

        draft = deepcopy(ACTIVE_WORKOUT_DRAFT)

    workout_id = save_workout_draft_to_db(draft)

    with DRAFT_LOCK:
        ACTIVE_WORKOUT_DRAFT = None

    return RedirectResponse(f"/workouts/{workout_id}", status_code=303)
```

Required service-oriented version:

```python
def finish_current_workout() -> int:
    draft = draft_repository.get_required()

    workout_id = workout_repository.create_completed_from_draft(draft)

    draft_repository.clear()

    return workout_id
```

The database insert and draft clear should be atomic when the draft moves to SQLite.

---

## 14. Analysis Model

The current load calculation considers:

* Exercise profile
* Number of reps
* Estimated relative intensity
* Session RPE
* Compound contribution
* Back-stress contribution

Simplified structure:

```python
set_score = (
    exercise_factor
    * rep_factor(reps)
    * intensity_factor(relative_intensity)
)

load_score = sum(set_scores) * rpe_factor(session_rpe)
```

Current RPE multiplier:

```python
def rpe_factor(session_rpe: int | float | None) -> float:
    if session_rpe is None:
        return 1.0

    return 0.7 + float(session_rpe) * 0.06
```

Current load labels:

```python
def workout_load_label(load_score: float) -> str:
    if load_score < 4:
        return "Light"
    if load_score < 8:
        return "Medium"
    if load_score < 14:
        return "Hard"
    return "Very hard"
```

These formulas are product heuristics, not validated medical or sports-science standards. They must be covered by tests before refactoring.

---

## 15. Testing Requirements

Add backend tests before moving logic.

Recommended structure:

```text
tests/
  test_analysis.py
  test_recovery.py
  test_recommendations.py
  test_draft_service.py
  test_workout_service.py
  test_backup.py
  test_api_current_workout.py
  test_api_stats.py
```

Minimum test coverage:

### Analysis

* e1RM with valid and invalid rep ranges
* Rep factor boundaries
* Intensity factor boundaries
* RPE multiplier
* Load label boundaries
* Compound score
* Back-stress score
* Unknown exercise profile fallback

### Draft

* Start draft
* Add exercise
* Add set
* Duplicate set
* Delete and renumber set
* Delete and reorder exercise
* Metadata with empty values
* Finish and persist
* Restart recovery after persistent draft is added

### Database

* Cascade delete workout
* Backup schema v1 restore
* Backup schema v2 restore
* Sequence reset
* Database reset and default exercise reseeding

### API

* Validation errors return JSON
* Optional RPE/back pain work correctly
* Missing current draft returns a stable response
* Finish returns created workout ID
* Stats endpoint returns consistent schema

---

## 16. Frontend Requirements

### Current Workout page

First React page to implement.

Required behavior:

* Load current draft from API
* Start workout without page reload
* Update live timer locally
* Add exercise
* Add set
* Duplicate set
* Delete set
* Delete exercise
* Edit RPE and lower-back pain
* Finish workout
* Display pending/error states
* Disable duplicate submissions
* Revalidate current workout after mutations

### Stats page

Use Recharts for:

* Volume trend
* Load trend
* Average intensity trend
* RPE trend
* Lower-back pain trend
* Per-exercise volume
* Estimated strength progression
* Load versus back-pain comparison

The API should provide raw values and semantic metadata. The frontend should control presentation.

### State management

Start with:

* React state
* TanStack Query for server state

Do not introduce Redux unless the application later requires complex client-only state.

### Offline operation

The deployed app must remain fully usable on a local network without internet access.

Frontend implementation rules:

* Bundle all JavaScript and CSS assets into the application build.
* Do not load scripts, styles, fonts, icons, charts, maps, or images from CDNs or other remote hosts at runtime.
* Do not require online services for workout logging, history, backup/restore, or analytics.
* Any future optional online feature must fail gracefully and must not block the core training log.

---

## 17. Docker and Build Plan

Development:

```text
FastAPI: http://localhost:8000
Vite:    http://localhost:5173
```

Vite proxy:

```ts
export default defineConfig({
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
```

Production build:

1. Build frontend with Node
2. Copy `frontend/dist` into the Python image
3. Serve static assets with FastAPI
4. Keep API and frontend on the same origin

Possible multi-stage Dockerfile:

```dockerfile
FROM node:22-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./
RUN npm run build


FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY --from=frontend-build /frontend/dist ./app/static

CMD ["/run.sh"]
```

---

## 18. Migration Plan

### Phase 1: Stabilize

* Add tests for current formulas
* Fix any remaining optional-form parsing issues
* Stop changing formulas during structural refactoring
* Define canonical stats response model

### Phase 2: Split backend

* Extract DB helpers
* Extract repositories
* Extract services
* Move routes into routers
* Keep existing behavior unchanged

### Phase 3: Persistent draft

* Add persistent draft storage
* Add migration
* Restore active draft after restart
* Preserve “only save completed workout on Finish”

### Phase 4: JSON API

* Add `/api/v1/current-workout`
* Add mutations for exercises and sets
* Add workout history endpoints
* Add stats endpoint
* Add API tests

### Phase 5: React shell

* Create Vite React TypeScript project
* Add routing
* Add API client
* Add shared theme
* Add app navigation

### Phase 6: Current Workout

* Implement full active-workout flow
* Keep Jinja `/` page as fallback
* Verify mobile UX

### Phase 7: Stats

* Replace custom CSS charts with Recharts
* Merge `/stats` and `/stats2`
* Add filtering and drill-down

### Phase 8: Remaining pages

* History
* Workout detail
* Workout edit
* Backup

### Phase 9: Cleanup

* Remove obsolete Jinja routes
* Remove duplicated CSS
* Remove `stats2`
* Add frontend build to CI
* Add backend tests to CI

---

## 19. Unresolved Questions

### Persistent draft

Choose one:

* SQLite draft tables
* Atomic JSON draft file

Recommended: SQLite.

### Exercise profiles

Choose one:

* Add columns directly to `exercises`
* Add separate `exercise_profiles` table
* Keep profiles in configuration

Recommended: separate profile fields stored in the database, with defaults created during migration.

### Units

Clarify how dumbbell weight is interpreted:

* Weight per dumbbell
* Combined weight

This affects tonnage and comparison metrics.

### Time handling

Current timestamps are naive local ISO strings.

Decide whether to:

* Keep local naive timestamps
* Store UTC and display local time

Recommended for long-term stability: store UTC timestamps and convert in UI.

### Stats semantics

Confirm whether “average intensity” should continue to mean:

```text
total weight / total reps
```

or whether the primary intensity metric should be percentage of e1RM.

Both may remain, but labels must distinguish them clearly.

### Recommendation scope

Clarify whether recommendations are:

* Whole-workout recommendations
* Per-exercise recommendations
* Both

Current code contains both workout and exercise-level analysis concepts.

### Multi-user support

Current app assumes one user and one active draft.

Confirm whether this will remain a single-user Home Assistant tool.

### Authentication

No application-level authentication is currently planned.

Confirm whether Home Assistant ingress is the only expected access-control layer.

### Home Assistant base path

Deferred.

When revisited, use centralized frontend URL generation and FastAPI root-path awareness rather than hardcoding a prefix throughout the application.

### Stats 2

Decide when to remove `/stats2`.

Recommended: remove it immediately after the React Stats page reaches parity.

### Repository database file

The repository has historically included updates to `data/training.db`.

Decide whether to:

* Remove it from Git tracking
* Keep a separate fixture database
* Generate test data through scripts

Recommended: ignore the runtime database and maintain explicit fixtures or seed scripts.

---

## 20. First Recommended Codex Task

Create a new branch and implement only backend stabilization.

Scope:

1. Add tests for analysis helpers
2. Split analysis logic from `app/main.py` into `app/services/analysis_service.py`
3. Preserve all existing formulas and outputs
4. Keep all current routes and Jinja pages working
5. Do not add React yet
6. Do not change database schema yet
7. Do not add Home Assistant path-prefix support
8. Run tests and verify application startup

Suggested branch:

```text
refactor/backend-analysis-service
```

Suggested commit sequence:

```text
test: add coverage for training analysis formulas
refactor: extract analysis service from main module
test: verify stats and workout analysis behavior
```

Acceptance criteria:

* Existing HTML pages still render
* Existing stats values are unchanged
* Analysis functions are independently importable
* Tests cover formula boundaries and fallback behavior
* `app/main.py` is materially smaller
* No database migration is required
* No UI behavior changes
  :::
