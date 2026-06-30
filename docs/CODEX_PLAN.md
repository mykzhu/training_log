# Training Log — Codex Plan Addendum: Home Assistant Prefix + Configurable Analysis Types

Repository: `mykzhu/training_log`  
Target branch: latest `master`  
Intended baseline: after 1.1.0 release / after Garmin Phase 15  
Purpose: add two user-requested changes with detailed, token-efficient instructions for Codex.

User requests:

1. Support URL prefixing so the app can open correctly from Home Assistant, including the add-on toolbox / Open Web UI button and Home Assistant ingress paths.
2. Make Analysis Types configurable: list them, add new ones, edit existing ones, and assign them to exercises.

---

## How Codex must use this plan

1. Pull latest `master`.
2. Re-read `docs/CODEX_PLAN.md`, this addendum, and the current code before editing.
3. Execute only the first unchecked phase unless explicitly told otherwise.
4. Do not mix the Home Assistant prefix work with analysis-type persistence.
5. Do not change Garmin scoring, workout recommendation logic, or exercise progression unless a phase explicitly asks for it.
6. Keep API changes explicit and regenerate OpenAPI/generated TypeScript when schemas change.
7. Run only the required checks for the phase, plus any tests touched by the change.
8. Update `docs/CODEX_PLAN.md` when each phase is complete.
9. Report changed files, commands run, manual checks, and any untested Home Assistant behavior.

---

## Current code facts to preserve

### Home Assistant / frontend routing

Current backend serves API routes first and then falls back to the React app for non-API paths. It rejects paths starting with `api/` from the SPA fallback.

Current backend fallback behavior:

```python
@app.get("/{path:path}", include_in_schema=False)
def serve_react_app(path: str = "") -> FileResponse:
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found.")
```

Current frontend API client fetches the path exactly as passed:

```typescript
const response = await fetch(path, { ...init, headers });
```

Current Vite config does not set a relative `base`, so built asset URLs may assume `/assets/...`:

```typescript
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    assetsDir: "assets",
  },
});
```

Implication: under a Home Assistant ingress prefix like `/api/hassio_ingress/<token>/`, absolute frontend routes, asset paths, and API fetches can lose the prefix unless the app handles a runtime base path.

### Analysis types

Current analysis profiles are hardcoded in `app/services/analysis_service.py`:

- `LOAD_PROFILES_BY_KEY`
- `PROFILE_LABELS_BY_KEY`
- `SUPPORTED_PROFILE_KEYS`
- `EXERCISE_PROFILE_KEYS_BY_NAME`

Exercises already store a `profile_key`.

Settings already lets the user choose an “Analysis type” for an exercise, but only from hardcoded profiles returned by `GET /api/v1/exercise-profiles`.

Current profile response only exposes:

```python
class ExerciseProfileResponse(AppBaseModel):
    key: str
    label: str
    category: str
```

Implication: adding/editing analysis types requires database persistence, migrations, API CRUD, schema changes, frontend UI, backup schema update, and replacing hardcoded profile lookup with DB-backed profile lookup.

---

# Recommended next phases

## [ ] Phase 16 — Home Assistant prefix/toolbox launch hardening

Branch:

```text
fix/ha-ingress-prefix-routing
```

### Goal

Make the app work from all expected Home Assistant entry points:

1. Home Assistant sidebar panel / ingress URL.
2. Home Assistant add-on page toolbox / “Open Web UI” button.
3. Direct local development root URL.
4. Deep links and browser refreshes from all of the above.

The app must not lose the URL prefix when navigating or calling APIs.

### Definition of “prefixing”

Support a runtime base path before the app route:

```text
/
          direct root
/history
          direct root deep link
/api/hassio_ingress/<token>/
          Home Assistant ingress root
/api/hassio_ingress/<token>/history
          Home Assistant ingress deep link
/custom/prefix/
          optional future reverse-proxy prefix
/custom/prefix/garmin?range=90
          optional future reverse-proxy deep link
```

The exact Home Assistant ingress token is dynamic and must never be hardcoded.

### Non-goals

- Do not change business logic.
- Do not change API schemas.
- Do not redesign UI.
- Do not change Garmin behavior.
- Do not change workout routes.
- Do not add a new router library.
- Do not require a compile-time Vite base for Home Assistant.
- Do not break direct root deployment.

### Expected user-visible result

When opening the add-on from Home Assistant:

- app loads instead of blank page;
- assets load;
- `/api/v1/...` calls succeed;
- navigation works;
- browser refresh on `/history`, `/settings`, `/garmin`, `/workouts/{id}`, `/exercises/{id}/stats` works;
- the Settings link, Garmin link, History links, and all React Router navigation preserve the Home Assistant prefix.

### Implementation strategy

Use a runtime base-path helper in the frontend and keep the backend SPA fallback robust.

#### Frontend: add runtime base-path helper

Create:

```text
frontend/src/utils/basePath.ts
```

Suggested functions:

```typescript
export function normalizeBasePath(value: string): string {
  const trimmed = value.trim();
  if (!trimmed || trimmed === "/") return "";
  return `/${trimmed.replace(/^\/+|\/+$/g, "")}`;
}

export function detectIngressBasePath(pathname = window.location.pathname): string {
  const segments = pathname.split("/").filter(Boolean);

  // Home Assistant ingress usually appears as:
  // /api/hassio_ingress/<token>/...
  if (segments[0] === "api" && segments[1] === "hassio_ingress" && segments[2]) {
    return `/${segments.slice(0, 3).join("/")}`;
  }

  return "";
}

export function appBasePath(): string {
  const configured = import.meta.env.VITE_APP_BASE_PATH;
  if (typeof configured === "string" && configured.trim()) {
    return normalizeBasePath(configured);
  }

  return detectIngressBasePath();
}

export function withAppBasePath(path: string): string {
  if (!path) return appBasePath() || "/";
  if (/^[a-z][a-z0-9+.-]*:/i.test(path)) return path;

  const base = appBasePath();
  if (!base) return path;

  if (path.startsWith("/")) {
    return `${base}${path}`;
  }

  return `${base}/${path}`;
}
```

Rules:

- If there is no prefix, behavior must be unchanged.
- If path is absolute URL, do not modify it.
- If path is `/api/v1/...`, return `/api/hassio_ingress/<token>/api/v1/...` under ingress.
- If path is `/settings`, React Router must navigate under the same base.
- Keep helper pure and testable.

#### Frontend: BrowserRouter basename

Update `frontend/src/App.tsx`:

```tsx
<BrowserRouter basename={appBasePath() || undefined}>
  ...
</BrowserRouter>
```

Rules:

- Import `appBasePath` from the helper.
- Do not manually prefix every `<Link to="/...">`.
- Keep route definitions as app-relative paths: `/`, `/history`, `/garmin`, etc.
- Verify `useNavigate()` keeps prefix automatically with basename.

#### Frontend: API client prefixing

Update `frontend/src/api/client.ts`:

```typescript
import { withAppBasePath } from "../utils/basePath";

const requestPath = withAppBasePath(path);
const response = await fetch(requestPath, { ...init, headers });
```

Rules:

- All existing API modules can keep calling `requestJson("/api/v1/...")`.
- Do not manually edit every API call.
- Do not prefix already absolute URLs.

#### Frontend: Vite relative assets

Update `frontend/vite.config.ts`:

```typescript
export default defineConfig({
  base: "./",
  plugins: [react()],
  ...
});
```

Reason:

- Built `index.html` should reference assets relatively, so it works under `/`, `/api/hassio_ingress/<token>/`, and any future prefix.

Verify built `frontend/dist/index.html` uses relative script/style asset references, not `/assets/...`.

#### Backend: optional prefix stripping / robust fallback

Most Home Assistant ingress proxies strip the ingress prefix before the request reaches the add-on. But the app should also be robust if a reverse proxy forwards the prefix unchanged.

Add optional environment config:

```python
APP_URL_PREFIX = os.getenv("APP_URL_PREFIX", "").strip("/")
```

Add helper in backend, for example `app/main.py`:

```python
def strip_app_url_prefix(path: str) -> str:
    prefix = config.APP_URL_PREFIX.strip("/")
    if not prefix:
        return path
    if path == prefix:
        return ""
    if path.startswith(f"{prefix}/"):
        return path[len(prefix) + 1:]
    return path
```

Use it in `serve_react_app(path)` before `get_frontend_file`.

Rules:

- Default must be empty and preserve current behavior.
- This is for non-HA reverse proxy deployments; frontend ingress detection still handles HA dynamically.
- Do not apply this to API router prefixes unless tests prove the reverse proxy forwards prefixed API paths into the backend. Prefer frontend prefixing for browser calls.

#### Backend: direct toolbox / Open Web UI support

Keep `config.yaml` values compatible with Home Assistant:

```yaml
ingress: true
ingress_port: 8000
ingress_entry: /
webui: "http://[HOST]:[PORT:8000]/"
ports:
  8000/tcp: 8000
```

Do not remove `webui` or `ports` in this phase.

If direct toolbox open still fails after prefix work, inspect the exact URL opened by Home Assistant and only then adjust `webui`/`ports`.

### Files expected to change

```text
frontend/vite.config.ts
frontend/src/utils/basePath.ts
frontend/src/api/client.ts
frontend/src/App.tsx
app/config.py
app/main.py
tests/test_frontend_routing_or_main.py     # name may differ
docs/CODEX_PLAN.md
```

Potentially update README/Home Assistant notes if there is already a deployment section.

### Tests

#### Frontend helper tests

Only add a frontend test framework if the repo already has one. If there is no frontend unit-test setup, avoid adding Vitest just for this phase unless explicitly needed.

Preferred if no frontend tests exist:

- keep helper simple and pure;
- rely on TypeScript typecheck/build;
- document manual smoke.

If frontend tests exist or are added later, cover:

```text
detectIngressBasePath("/") -> ""
detectIngressBasePath("/history") -> ""
detectIngressBasePath("/api/hassio_ingress/abc123/") -> "/api/hassio_ingress/abc123"
detectIngressBasePath("/api/hassio_ingress/abc123/history") -> "/api/hassio_ingress/abc123"
withAppBasePath("/api/v1/current-workout") under ingress -> "/api/hassio_ingress/abc123/api/v1/current-workout"
withAppBasePath("/settings") under ingress -> "/api/hassio_ingress/abc123/settings"
withAppBasePath("https://example.com/x") -> unchanged
```

#### Backend tests

Add lightweight backend tests for `strip_app_url_prefix` if implemented:

```text
prefix empty, path "history" -> "history"
prefix "custom/prefix", path "custom/prefix" -> ""
prefix "custom/prefix", path "custom/prefix/history" -> "history"
prefix "custom/prefix", path "other/history" -> "other/history"
```

Add SPA fallback test if existing test infrastructure supports it:

```text
GET /history returns index.html
GET /assets/missing.js returns 404
GET /api/unknown returns 404 JSON, not index.html
```

### Required checks

```bash
python -m unittest discover -s tests

cd frontend
npm run typecheck
npm run build
cd ..
```

### Manual smoke matrix

Run after build/start.

Direct root:

```text
http://localhost:8000/
http://localhost:8000/history
http://localhost:8000/settings
http://localhost:8000/garmin
http://localhost:8000/exercises/1/stats
browser refresh on each route
API calls from each page
```

Simulated Home Assistant ingress in browser:

```text
Open /api/hassio_ingress/faketoken/
Open /api/hassio_ingress/faketoken/history
Open /api/hassio_ingress/faketoken/settings
Open /api/hassio_ingress/faketoken/garmin
Click nav links
Trigger API calls
Refresh deep links
```

Real Home Assistant:

```text
Open from sidebar panel
Open from add-on toolbox / Open Web UI
Refresh page
Navigate to History
Navigate to Settings
Navigate to Garmin
Start active workout
Open existing workout detail
Open exercise stats
Garmin sync button still calls API
Backup export still downloads
```

### Acceptance criteria

- Direct root deployment still works.
- Home Assistant ingress route preserves prefix during navigation.
- Home Assistant toolbox/Open Web UI route opens the app.
- Built assets load under prefixed URL.
- API calls use the same runtime prefix as the page.
- Browser refresh on deep links works.
- No API schema changed.
- No Garmin or workout behavior changed.
- Backend tests pass.
- Frontend typecheck/build pass.

---

## [ ] Phase 17 — Configurable Analysis Types

Branch:

```text
feat/configurable-analysis-types
```

### Goal

Allow the user to create and edit Analysis Types from Settings.

An Analysis Type defines how an exercise contributes to load/recovery calculations:

```text
key
label
category
exercise_factor
compound_factor
back_factor
active/inactive
sort order
```

Exercises should continue to reference an analysis type by `profile_key`.

### User-visible result

Settings should have a dedicated “Analysis types” section where the user can:

- see existing built-in analysis types;
- add a custom analysis type;
- edit label/category/factors for existing analysis types;
- deactivate unused custom analysis types;
- see which exercises use each type;
- assign any active analysis type to an exercise;
- understand that editing factors affects future displayed analysis and historical recalculation.

### Non-goals

- Do not change workout tables.
- Do not change set logging.
- Do not add per-set custom factors.
- Do not add delete for profiles used by exercises.
- Do not introduce multiple profiles per exercise.
- Do not redesign recommendation algorithms.
- Do not change Garmin logic.
- Do not change exercise weight presets except where required for compatibility.
- Do not make profile keys editable after creation.

### Current model

Current hardcoded profile shape:

```python
{
  "category": "heavy compound",
  "exercise_factor": 1.8,
  "compound_factor": 1.8,
  "back_factor": 1.8,
}
```

Current labels are separate from factors.

Current `exercises.profile_key` already stores the selected profile.

### Proposed database schema

Add migration:

```text
app/migrations/v007_analysis_profiles.py
```

Create table:

```sql
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
```

Indexes:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_profiles_label_nocase
ON analysis_profiles(label COLLATE NOCASE);

CREATE INDEX IF NOT EXISTS idx_analysis_profiles_active_order
ON analysis_profiles(is_active, sort_order, label);
```

Seed all current built-in profiles into `analysis_profiles`.

Rules:

- Preserve all existing keys:
  - `deadlift`
  - `squats`
  - `db_squats`
  - `bench_press`
  - `incline_bench_press`
  - `db_bench_press`
  - `shoulder_press`
  - `db_shoulder_press`
  - `ez_curl`
  - `triceps_pushdown`
  - `crunches`
  - old compatibility keys: `db_row`, `triceps_extension`, `lateral_raise`, `accessory`
- Existing exercise `profile_key` values must remain valid.
- Built-in profiles may be edited, but not deleted.
- Profile `key` is immutable.
- `accessory` must always exist and remain a fallback.
- If an unknown exercise profile is encountered, fallback to `accessory`.

### Backup schema

This phase changes persisted user configuration. Bump backup schema from `4` to `5`.

Add `analysis_profiles` to schema 5 backup export.

Restore rules:

- Schema 1-4 backups do not contain `analysis_profiles`; restore should seed default profiles during DB init/migration.
- Schema 5 backups restore `analysis_profiles`.
- Restore must reject invalid profile rows:
  - empty key;
  - invalid key format;
  - empty label;
  - negative factors;
  - duplicate labels ignoring case;
  - missing `accessory`;
  - exercise references to missing profile keys.
- Restore must not remove profile keys still referenced by exercises unless the restore payload contains compatible exercises and profiles together.
- Restore schema 5 must still exclude Garmin tokens.

### API design

Replace read-only profiles with CRUD-style routes under existing prefix:

```text
GET    /api/v1/exercise-profiles
POST   /api/v1/exercise-profiles
PATCH  /api/v1/exercise-profiles/{profile_key}
DELETE /api/v1/exercise-profiles/{profile_key}   optional, only if unused and non-builtin
```

Recommendation: implement GET/POST/PATCH first. DELETE can be omitted in this phase unless simple.

#### GET response

Keep old clients working by preserving `key`, `label`, `category`.

Add fields:

```python
class ExerciseProfileResponse(AppBaseModel):
    key: str
    label: str
    category: str
    exercise_factor: float
    compound_factor: float
    back_factor: float
    is_builtin: bool
    is_active: bool
    sort_order: int
    exercise_count: int
```

Response:

```python
class ExerciseProfilesResponse(AppBaseModel):
    profiles: list[ExerciseProfileResponse]
```

Sorting:

```text
active first
sort_order ascending
label ascending
```

#### POST request

```python
class ExerciseProfileCreateRequest(AppBaseModel):
    key: str | None = Field(default=None, min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=120)
    exercise_factor: float = Field(ge=0, le=5)
    compound_factor: float = Field(ge=0, le=5)
    back_factor: float = Field(ge=0, le=5)
    is_active: bool = True
```

Rules:

- If key omitted, generate from label:
  - lowercase;
  - trim;
  - replace non-alphanumeric with underscore;
  - collapse underscores;
  - strip underscores;
  - max length 80;
  - reject if empty.
- Reject duplicate key.
- Reject duplicate label ignoring case.
- New custom profiles have `is_builtin = false`.
- Assign `sort_order` after current max.

#### PATCH request

```python
class ExerciseProfileUpdateRequest(AppBaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, min_length=1, max_length=120)
    exercise_factor: float | None = Field(default=None, ge=0, le=5)
    compound_factor: float | None = Field(default=None, ge=0, le=5)
    back_factor: float | None = Field(default=None, ge=0, le=5)
    is_active: bool | None = None
```

Rules:

- Key is immutable.
- Reject empty patch.
- Reject duplicate label ignoring case.
- Built-ins can be edited but cannot be deleted.
- Do not allow deactivating `accessory`.
- Do not allow deactivating a profile currently used by active exercises unless the UI/API explicitly shows a warning and user confirms. Simpler first phase: reject deactivation when `exercise_count > 0`.
- Existing exercises assigned to an inactive profile remain valid if restored from backup, but UI should not offer inactive profiles for new assignments except the current exercise's own inactive profile.

#### DELETE optional

Only implement if it does not expand the phase too much.

Rules:

- 404 if missing.
- 409 if built-in.
- 409 if any exercise references it.
- Delete only unused custom profiles.

### Repository layer

Add:

```text
app/repositories/analysis_profiles.py
```

Functions:

```python
normalize_profile_key(value: str) -> str
profile_key_from_label(label: str) -> str
list_analysis_profiles(include_inactive: bool = True) -> list[dict]
get_analysis_profile(profile_key: str) -> dict | None
get_analysis_profiles_by_key(include_inactive: bool = True) -> dict[str, dict]
create_analysis_profile(payload) -> dict
update_analysis_profile(profile_key, payload) -> dict | None
delete_analysis_profile(profile_key) -> bool
profile_exercise_counts() -> dict[str, int]
ensure_default_analysis_profiles(conn) -> None
```

Validation exceptions:

```python
DuplicateProfileKeyError
DuplicateProfileLabelError
ProfileInUseError
BuiltinProfileDeleteError
InvalidProfileKeyError
AccessoryProfileError
```

Keep SQL in repository module.

### Service layer

Refactor `app/services/analysis_service.py`.

Split static defaults from runtime DB-backed behavior.

Suggested files:

```text
app/services/default_analysis_profiles.py
app/services/analysis_service.py
app/repositories/analysis_profiles.py
```

`default_analysis_profiles.py` contains immutable defaults:

```python
DEFAULT_LOAD_PROFILES_BY_KEY
DEFAULT_PROFILE_LABELS_BY_KEY
DEFAULT_EXERCISE_PROFILE_KEYS_BY_NAME
DEFAULT_PROFILE_ORDER
DEFAULT_PROFILE_KEY = "accessory"
```

`analysis_service.py` responsibilities:

```python
profile_key_for_exercise_name(exercise_name: str) -> str
list_exercise_profiles() -> list[dict]
is_supported_profile_key(profile_key: str) -> bool
get_exercise_load_profile(exercise_name: str, profile_key: str | None = None) -> dict
calculate_workout_load_metrics(...)
```

Runtime behavior:

- `list_exercise_profiles()` returns DB profiles if DB initialized; otherwise defaults.
- `get_exercise_load_profile(..., profile_key)` returns DB profile if available, else default by key, else fallback `accessory`.
- `profile_key_for_exercise_name()` can keep default name-fragment inference for new exercise creation.
- Calculations should avoid one DB query per set/exercise when possible:
  - load profile map once per calculation;
  - pass map into helper;
  - or cache for request scope.
- Do not add a global unbounded cache unless invalidated on profile edits.

### Exercise API behavior

Current exercise create/update already accepts `profile_key`.

Update validation:

- `create_exercise(... profile_key=...)` must accept active custom profile keys.
- If profile_key is missing, infer from exercise name using default name inference.
- If inferred key is not present/active, fallback `accessory`.
- `update_exercise(... profile_key=...)` must reject missing profile keys.
- Exercise listing must include current profile key even if inactive.
- Settings UI must display the label for inactive current profile.

Files likely touched:

```text
app/repositories/exercises.py
app/routes/api_exercises.py
app/schemas.py
app/services/analysis_service.py
app/services/default_analysis_profiles.py
app/repositories/analysis_profiles.py
```

### Frontend API/types

Update:

```text
frontend/src/api/exercises.ts
frontend/src/api/types.ts
frontend/src/api/generated.ts
docs/openapi.json
```

New API helpers:

```typescript
getExerciseProfiles()
createExerciseProfile(payload)
updateExerciseProfile(profileKey, payload)
deleteExerciseProfile(profileKey) // only if backend implements delete
```

Types:

```typescript
export type ExerciseProfile = {
  key: string;
  label: string;
  category: string;
  exercise_factor: number;
  compound_factor: number;
  back_factor: number;
  is_builtin: boolean;
  is_active: boolean;
  sort_order: number;
  exercise_count: number;
};
```

### Settings UI

Refactor `frontend/src/pages/SettingsPage.tsx` enough to avoid a giant component if practical.

Suggested split:

```text
frontend/src/components/settings/GarminSettingsPanel.tsx
frontend/src/components/settings/AnalysisProfilesPanel.tsx
frontend/src/components/settings/ExerciseSettingsPanel.tsx
frontend/src/components/settings/WeightEditor.tsx
```

Keep split minimal if it risks broad churn.

#### Add Analysis Types panel

Position:

```text
Settings
  Garmin
  Analysis types
  Exercises and weights
```

Analysis Types panel should show:

- profile label;
- immutable key;
- category;
- exercise factor;
- compound factor;
- back factor;
- active/inactive;
- built-in/custom;
- exercise count;
- warning text: “Changing factors recalculates displayed historical load analysis.”

Profile card edit controls:

```text
Label input
Category input
Exercise factor number input
Compound factor number input
Back factor number input
Active toggle
Save button
```

Add-profile form:

```text
Label
Key optional / auto generated preview
Category
Exercise factor
Compound factor
Back factor
Add
```

Validation UI:

- label required;
- category required;
- factors must be 0..5;
- key must match slug format if provided;
- duplicate errors from backend displayed clearly;
- prevent saving unchanged profile;
- disable deactivation when `exercise_count > 0`;
- show “Used by N exercises.”

#### Exercise profile dropdown behavior

In Add Exercise and Exercise cards:

- list active profiles;
- include current inactive profile if an exercise already uses it;
- label inactive profiles as `(inactive)`;
- group or sort active first;
- when selecting an analysis type, show its category and factors in small muted text if easy.

Do not require editing exercise weights when only profile changes.

### CSS / mobile

Add styles for:

```text
.analysis-profile-panel
.analysis-profile-grid
.analysis-profile-card
.analysis-profile-form
.profile-factor-grid
.profile-meta
.profile-warning
```

Mobile rules:

- cards one column below mobile breakpoint;
- factor inputs in 2-column or 1-column grid;
- Save/Add buttons full width on narrow screens;
- avoid horizontal scroll.

### OpenAPI/contracts

Because this phase changes API schemas:

```bash
python scripts/generate_api_contracts.py
```

Then ensure:

```text
docs/openapi.json updated
frontend/src/api/generated.ts updated
frontend/src/api/types.ts updated if manually maintained
```

### Backup service

Update:

```text
app/services/backup_service.py
```

Required changes:

- `BACKUP_SCHEMA_VERSION = 5`
- include `analysis_profiles` in export;
- validate profile rows on import;
- restore profile rows before restoring exercises;
- preserve schema 1-4 restore behavior;
- ensure default profiles are available after older backup restore;
- ensure Garmin tokens remain excluded.

Schema 5 backup content should include:

```json
{
  "schema_version": 5,
  "analysis_profiles": [
    {
      "key": "deadlift",
      "label": "Deadlift",
      "category": "heavy compound",
      "exercise_factor": 1.8,
      "compound_factor": 1.8,
      "back_factor": 1.8,
      "is_builtin": true,
      "is_active": true,
      "sort_order": 10
    }
  ]
}
```

### Data migration details

Migration should be idempotent.

Pseudo-flow:

```python
def migrate(conn):
    create analysis_profiles table if missing
    seed defaults with INSERT ... ON CONFLICT DO NOTHING
    ensure all exercises.profile_key values exist:
        for each distinct unknown profile_key:
            insert custom inactive profile with label derived from key
            category = "imported"
            factors = accessory defaults
            is_builtin = 0
            is_active = 0
```

Reason:

- Protects old/invalid/custom DBs.
- Avoids breaking calculations if an exercise references a profile key not known by defaults.

### Backend tests

Add tests for repository:

```text
default profiles are seeded
list profiles includes built-ins
create custom profile with explicit key
create custom profile with generated key
reject duplicate key
reject duplicate label ignoring case
reject invalid key
reject negative factor
update custom profile factors
update built-in profile factors
cannot deactivate accessory
cannot deactivate profile used by exercise
unknown profile fallback returns accessory
unknown exercise name infers accessory
existing exercise with custom profile calculates custom load factors
```

Add API tests:

```text
GET /api/v1/exercise-profiles returns new fields
POST /api/v1/exercise-profiles creates profile
PATCH /api/v1/exercise-profiles/{key} edits profile
POST exercise accepts custom profile_key
PATCH exercise accepts custom profile_key
PATCH exercise rejects missing profile_key
inactive profile not accepted for new assignment unless rules allow it
```

Add calculation tests:

```text
custom profile exercise_factor changes load_score
custom compound_factor changes compound_score
custom back_factor changes back_stress_score
editing profile affects recalculated historical workout analysis
default built-in profile values remain same as before migration
```

Add backup tests:

```text
schema 5 export includes analysis_profiles
schema 5 restore restores custom profile
schema 5 restore restores exercise using custom profile
schema 1-4 restore seeds default profiles
schema 5 restore rejects duplicate labels
schema 5 restore rejects missing profile referenced by exercise
schema 5 backup excludes Garmin tokens
schema 5 restore keeps Garmin daily metrics behavior from schema 4
```

### Frontend checks

```bash
cd frontend
npm run typecheck
npm run build
```

### Backend checks

```bash
python -m unittest discover -s tests
```

### Manual smoke

```text
Open Settings
See Analysis types section
Add custom profile: “Cable row”
Assign custom profile to an exercise
Log workout using that exercise
Open workout detail and verify load metrics use custom factors
Edit custom profile factor and refresh workout detail
Verify load metrics update
Try duplicate label and see clear error
Try negative factor and see clear error
Try deactivating profile used by an exercise and see clear error
Edit built-in profile label/category/factors
Open Add Exercise profile dropdown
Open existing exercise profile dropdown
Backup export
Backup validate
Backup restore into empty DB
Schema 1/2/3/4 restore still works
Mobile Settings page
```

### Acceptance criteria

- User can add a new Analysis Type from Settings.
- User can edit label/category/factors of existing Analysis Types.
- Exercises can be assigned to custom Analysis Types.
- Load metrics use DB-backed custom factors.
- Existing built-in profile behavior is preserved after migration.
- Unknown/missing profile keys safely fall back to `accessory`.
- Backup schema 5 includes analysis profiles.
- Restoring schema 1-4 still works.
- Restoring schema 5 with custom profiles works.
- OpenAPI and generated TypeScript contracts are current.
- Backend tests pass.
- Frontend typecheck/build pass.
- No Garmin behavior changed.
- No Home Assistant prefix behavior changed beyond Phase 16 work.

---

## [ ] Phase 18 — Garmin insights unification and correctness pass

Branch:

```text
refactor/garmin-insights-shared
```

Keep this after the two user-requested features unless the user explicitly reprioritizes.

Goal:

- Avoid separate Garmin interpretation logic between Current Workout and `/garmin`.
- Keep readiness scoring behavior stable.
- Share date/baseline/freshness helpers.
- Add fixture tests proving both representations agree.

Do not change Garmin scoring thresholds in this phase.

---

## [ ] Phase 19 — Global Stats page componentization

Branch:

```text
refactor/stats-page-components
```

Goal:

- Split large global Stats page into focused components without behavior changes.

Rules:

- No algorithm changes.
- No chart redesign.
- No new endpoints.
- Preserve mobile behavior.
- Do not mix with Analysis Types.

---

## Always-run release checks

Before any release:

```bash
python -m unittest discover -s tests

cd frontend
npm ci
npm run typecheck
npm run build
cd ..

docker build -t training-log:release-candidate .
```

---

## Release checklist

- Update `CHANGELOG.md`.
- Bump `config.yaml`.
- Confirm `docs/openapi.json` is current.
- Confirm generated TypeScript API/types are current.
- Run backend tests.
- Run frontend typecheck.
- Run frontend build.
- Run Docker build.
- Smoke Home Assistant ingress.
- Smoke toolbox/Open Web UI.
- Smoke active workout.
- Smoke read-only workout detail.
- Smoke edit workout.
- Smoke global stats.
- Smoke exercise stats.
- Smoke Garmin settings.
- Smoke Garmin current workout recovery.
- Smoke Garmin Stats page.
- Smoke Settings Analysis Types.
- Smoke backup export/validate/restore.
- Scan repository for runtime DBs, backups, logs, Garmin tokens, and secrets.
- Tag the release.
