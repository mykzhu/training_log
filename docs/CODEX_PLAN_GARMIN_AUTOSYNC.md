# Codex Plan Addendum — Garmin Auto-Sync Switch

Repository: `mykzhu/training_log`  
Target baseline: after Garmin 1.1.0 / Phase 15  
Purpose: add a Settings switch so Garmin metrics can sync automatically without pressing “Sync 35 days” manually every morning.

Recommended phase ordering:

```text
Phase 16 — Home Assistant prefix/toolbox launch hardening
Phase 17 — Garmin auto-sync switch
Phase 18 — Configurable Analysis Types
Phase 19 — Garmin insights unification
Phase 20 — Global Stats componentization
```

Reason: Garmin auto-sync is smaller and directly improves the current Garmin feature. Configurable Analysis Types is larger and should not be mixed with scheduler/background work.

---

## [x] Phase 17 — Garmin auto-sync switch

Branch:

```text
feat/garmin-autosync-settings
```

### Goal

Add an optional Garmin auto-sync setting in Settings.

The user should not need to manually open Settings and press **Sync 35 days** every day.

The app should be able to:

- remember whether Garmin auto-sync is enabled;
- sync Garmin metrics automatically once per day;
- show last auto-sync status in Settings;
- allow manual sync to remain available;
- avoid duplicate repeated sync attempts;
- never sync if Garmin is disconnected or MFA/token state is invalid;
- never expose Garmin credentials/tokens in DB, frontend, logs, or backups.

---

## User-visible behavior

### Settings → Garmin

Add an **Auto-sync** section/card inside the existing Garmin Settings panel.

Controls:

```text
[ ] Auto-sync Garmin daily
Sync after: [07:00]
Sync range: [35] days
```

For first implementation, acceptable simplified UI:

```text
[ ] Auto-sync Garmin daily
```

with fixed defaults:

```text
sync_after_local_time = 07:00
sync_days = 35
```

Show status fields:

```text
Auto-sync: Enabled / Disabled
Next check: ...
Last auto-sync attempt: ...
Last successful auto-sync: ...
Last result: Saved N date(s), skipped M, warnings K
Last error: ...
```

Keep existing manual button:

```text
Sync 35 days
```

Manual sync must still work even if auto-sync is disabled.

### Default behavior

Default:

```text
auto_sync_enabled = false
sync_after_local_time = 07:00
sync_days = 35
```

Reason:

- Do not surprise users by using Garmin API in the background without explicit opt-in.
- User turns it on from Settings.

### Intended daily routine

After user enables auto-sync:

- Garmin watch syncs sleep/HRV in the morning.
- Training Log backend wakes up periodically.
- If local time is after configured sync time and no successful auto-sync happened today, it runs `syncGarmin(35)`.
- Current Workout and `/garmin` then use fresh local persisted metrics.

---

## Non-goals

- Do not add Home Assistant automation integration in this phase.
- Do not add cron configuration UI beyond a simple daily local time.
- Do not add multiple schedules.
- Do not add external scheduler dependencies unless absolutely necessary.
- Do not sync more often than once per day by default.
- Do not call Garmin during page render.
- Do not change Garmin readiness scoring.
- Do not change Garmin stats interpretation.
- Do not change backup schema unless new persisted settings are included in backup.
- Do not store Garmin username/password in DB.
- Do not store Garmin tokens in DB or backups.

---

## Data model

Add persistent settings for Garmin auto-sync.

Preferred simple table:

```sql
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Alternative, if repo already has a settings table by the time Codex runs, reuse it.

Settings keys:

```text
garmin.auto_sync.enabled
garmin.auto_sync.sync_after_local_time
garmin.auto_sync.sync_days
garmin.auto_sync.last_attempt_at
garmin.auto_sync.last_success_at
garmin.auto_sync.last_result_json
garmin.auto_sync.last_error
garmin.auto_sync.last_checked_local_date
```

Simpler alternative:

```sql
CREATE TABLE IF NOT EXISTS garmin_sync_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    auto_sync_enabled INTEGER NOT NULL DEFAULT 0 CHECK (auto_sync_enabled IN (0, 1)),
    sync_after_local_time TEXT NOT NULL DEFAULT '07:00',
    sync_days INTEGER NOT NULL DEFAULT 35 CHECK (sync_days BETWEEN 1 AND 90),
    last_attempt_at TEXT,
    last_success_at TEXT,
    last_error TEXT,
    last_result_json TEXT,
    updated_at TEXT NOT NULL
);
```

Preferred for this phase: `garmin_sync_settings`, because it is explicit and easier for Codex/tests.

### Migration

Add migration:

```text
app/migrations/v00X_garmin_auto_sync_settings.py
```

Use next available migration number.

Migration must be idempotent.

Create one default row:

```sql
INSERT OR IGNORE INTO garmin_sync_settings (
    id,
    auto_sync_enabled,
    sync_after_local_time,
    sync_days,
    updated_at
)
VALUES (1, 0, '07:00', 35, current_timestamp);
```

### Backup schema

If persisted settings are included in backup, bump backup schema.

Recommended:

- If current backup schema is still `4`, bump to `5` for Garmin auto-sync settings.
- If configurable analysis profiles already bumped backup to `5`, then auto-sync should either:
  - be included in schema `6`, or
  - be folded into the same next schema if phases are combined later.

Because the current recommended order is:

```text
Phase 17 Auto-sync
Phase 18 Analysis Types
```

then:

```text
Phase 17: backup schema 5 adds garmin_sync_settings
Phase 18: backup schema 6 adds analysis_profiles
```

But if you want to keep Analysis Types as schema 5, then make auto-sync settings not exported in backup in Phase 17, or explicitly reorder schemas.

Preferred decision for Codex:

```text
Do not export Garmin auto-sync settings in backups in the first auto-sync phase.
```

Reason:

- Auto-sync is operational environment config.
- It is safe to re-enable manually after restore.
- Avoids consuming backup schema 5 before Analysis Types.
- Avoids surprise background sync after restoring a backup to another Home Assistant instance.

Document this explicitly:

```text
Garmin auto-sync settings are intentionally not exported in backup schema 4/5.
After restore, auto-sync is disabled by default and must be re-enabled.
```

---

## API design

Add routes under existing Garmin API prefix:

```text
GET   /api/v1/garmin/auto-sync
PATCH /api/v1/garmin/auto-sync
```

### GET response

```python
class GarminAutoSyncSettingsResponse(AppBaseModel):
    enabled: bool
    sync_after_local_time: str
    sync_days: int
    last_attempt_at: str | None
    last_success_at: str | None
    last_error: str | None
    last_result: dict[str, Any] | None
    next_eligible_at: str | None
    timezone: str
```

Rules:

- `timezone` should use configured `APP_TIMEZONE`.
- `next_eligible_at` should be based on local date/time and last success.
- If disabled, `next_eligible_at` may be `None`.

### PATCH request

```python
class GarminAutoSyncSettingsUpdateRequest(AppBaseModel):
    enabled: bool | None = None
    sync_after_local_time: str | None = Field(
        default=None,
        pattern=r"^\d{2}:\d{2}$",
    )
    sync_days: int | None = Field(default=None, ge=1, le=90)
```

Validation:

- Reject empty patch.
- `sync_after_local_time` must be valid `HH:MM` 24-hour local time.
- Reject invalid hours/minutes even if regex passes:
  - hour 0..23;
  - minute 0..59.
- `sync_days` must be 1..90, same upper bound as manual sync request.
- Do not require Garmin to be connected to enable the switch, but show disconnected state in UI.
- Alternatively, allow enabling only when connected. Simpler UX: allow enabling, but scheduler skips until connected.

### Manual sync response interaction

Existing manual sync endpoint should update Garmin status as it already does.

Manual sync may optionally update:

```text
last_success_at
last_result_json
last_error = null
```

But do not mark it as `last_auto_sync_attempt_at` unless naming is generic.

Preferred names:

```text
last_auto_attempt_at
last_auto_success_at
last_auto_error
last_auto_result_json
```

Manual sync should not overwrite auto-specific fields except perhaps shared latest metric data.

---

## Backend service design

Add:

```text
app/services/garmin_auto_sync_service.py
app/repositories/garmin_sync_settings.py
```

Repository responsibilities:

```python
get_garmin_auto_sync_settings(conn=None) -> dict
update_garmin_auto_sync_settings(payload, conn=None) -> dict
record_garmin_auto_sync_attempt(...)
record_garmin_auto_sync_success(...)
record_garmin_auto_sync_error(...)
```

Service responsibilities:

```python
is_auto_sync_due(settings, now_local, latest_success_at) -> bool
next_eligible_auto_sync_at(settings, now_local) -> datetime | None
run_garmin_auto_sync_once() -> dict
```

### Due logic

Auto-sync is due when all are true:

```text
auto_sync_enabled is true
Garmin is connected / usable token exists
local current time >= sync_after_local_time
last_auto_success_at is not today in APP_TIMEZONE
no auto-sync attempt is currently running
```

Optional retry behavior:

```text
If last attempt failed today:
  allow one retry after 2 hours
  cap retries to 3 attempts per local day
```

Simpler first implementation:

```text
If failed today, do not retry until tomorrow.
Manual Sync 35 days remains available.
```

Preferred first implementation:

```text
One automatic attempt per day.
Manual sync remains available for retries.
```

This keeps behavior predictable and avoids hammering Garmin.

### Sync days

Use settings `sync_days`, default 35.

Call existing Garmin sync logic, not duplicated code.

There should be one underlying service function used by both:

```text
manual sync endpoint
auto-sync worker
```

If current sync logic lives in route code, extract it into service first.

---

## Scheduler design

Add background scheduler on FastAPI startup.

Preferred implementation: no new dependencies.

In `app/main.py` startup:

```python
@app.on_event("startup")
async def on_startup():
    ...
    start_garmin_auto_sync_scheduler(app)
```

But current startup may be sync function. Use whatever style is compatible with current code.

Suggested scheduler:

```python
async def garmin_auto_sync_loop(stop_event):
    while not stop_event.is_set():
        try:
            await run_garmin_auto_sync_if_due()
        except Exception:
            logger.exception("garmin.auto_sync.loop_error")
        await wait_with_stop(stop_event, seconds=3600)
```

Interval:

```text
Check once per hour.
```

Reason:

- Good enough for daily sync.
- Low risk.
- Avoids frequent Garmin calls.
- Hourly is enough if sync_after is 07:00; it will run between 07:00 and 08:00.

For development/testing, allow env override:

```text
GARMIN_AUTO_SYNC_CHECK_INTERVAL_SECONDS=3600
```

Rules:

- Minimum interval clamp in production code: no less than 300 seconds.
- Tests can call service directly without waiting.

### Shutdown

On shutdown:

- cancel background task cleanly;
- do not leave warnings about pending tasks.

If using `asyncio.create_task`, store task on `app.state`.

### Multi-worker safety

If app may run multiple workers later, avoid two workers syncing simultaneously.

For current Home Assistant add-on likely single-process. Still add basic DB lock field or in-process lock.

Minimum:

```python
_auto_sync_lock = asyncio.Lock()
```

Better:

```sql
last_attempt_at is written before sync starts
```

Due logic should avoid running again if an attempt is already recorded today.

Acceptance for first phase:

- in-process lock is enough;
- document that multi-worker deployments are not targeted.

---

## Logging

Add logs without secrets:

```text
garmin.auto_sync.skip disabled
garmin.auto_sync.skip disconnected
garmin.auto_sync.skip not_due
garmin.auto_sync.start days=35
garmin.auto_sync.success saved=N skipped=M warnings=K
garmin.auto_sync.error error_type=...
```

Rules:

- Do not log Garmin username/password.
- Do not log tokens.
- Do not log raw Garmin payload.
- Do not log full exception if it may include credentials; sanitize if needed.
- Error message stored in DB should be concise and non-secret.

---

## Frontend Settings UI

Update existing Garmin panel in:

```text
frontend/src/pages/SettingsPage.tsx
```

or split into component if already planned:

```text
frontend/src/components/settings/GarminSettingsPanel.tsx
```

Add state:

```typescript
const [garminAutoSync, setGarminAutoSync] = useState<GarminAutoSyncSettings | null>(null);
const [garminAutoSyncDraft, setGarminAutoSyncDraft] = useState(...);
const [garminAutoSyncPending, setGarminAutoSyncPending] = useState(false);
```

API helpers:

```text
frontend/src/api/garmin.ts
```

Add:

```typescript
getGarminAutoSyncSettings()
updateGarminAutoSyncSettings(payload)
```

Types:

```typescript
export type GarminAutoSyncSettings = {
  enabled: boolean;
  sync_after_local_time: string;
  sync_days: number;
  last_attempt_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  last_result: Record<string, unknown> | null;
  next_eligible_at: string | null;
  timezone: string;
};
```

UI copy:

```text
Auto-sync Garmin daily
Runs once per day after the selected local time. Uses the same local Garmin import as Sync 35 days. No Garmin request is made while pages render.
```

Disabled/disconnected state:

If Garmin is disconnected:

```text
Auto-sync is enabled, but Garmin is not connected. Connect Garmin for automatic sync to run.
```

Status display:

```text
Last automatic attempt: Jun 30, 07:12
Last automatic success: Jun 30, 07:12
Next eligible run: Jul 1, after 07:00
Last result: Saved 2 dates, skipped 33, warnings 0
```

Buttons:

```text
Save auto-sync settings
Sync 35 days now
```

Rules:

- Save button disabled if draft unchanged.
- Toggle should not immediately run sync; scheduler will run when due.
- Manual “Sync 35 days” remains explicit.
- After manual sync, refresh Garmin status and auto-sync settings.
- After saving auto-sync settings, refresh auto-sync settings.

Mobile:

- Toggle and fields should not overflow.
- Buttons stack on narrow screens.

---

## OpenAPI and generated TypeScript

Because this phase adds API schemas:

```bash
python scripts/generate_api_contracts.py
```

Update:

```text
docs/openapi.json
frontend/src/api/generated.ts
frontend/src/api/types.ts
```

If the repo manually maintains `types.ts`, update it explicitly.

---

## Files likely to change

```text
app/config.py
app/main.py
app/migrations/v00X_garmin_auto_sync_settings.py
app/repositories/garmin_sync_settings.py
app/routes/api_garmin.py
app/schemas.py
app/services/garmin_service.py
app/services/garmin_auto_sync_service.py
docs/openapi.json
frontend/src/api/garmin.ts
frontend/src/api/generated.ts
frontend/src/api/types.ts
frontend/src/pages/SettingsPage.tsx
frontend/src/styles.css
tests/test_garmin_auto_sync.py
docs/CODEX_PLAN.md
```

Possibly:

```text
app/services/backup_service.py
tests/test_backup_service.py
```

Only if Codex chooses to export/import auto-sync settings. Preferred first phase: do not include in backups.

---

## Backend tests

Add `tests/test_garmin_auto_sync.py`.

Test settings repository:

```text
default settings row exists after migration
default enabled is false
default sync_after_local_time is 07:00
default sync_days is 35
PATCH enabled true persists
PATCH sync_after_local_time persists
PATCH sync_days persists
reject invalid HH:MM values
reject sync_days > 90
reject empty PATCH
```

Test due logic:

```text
disabled -> not due
enabled but disconnected -> not due / skipped
enabled connected before sync time -> not due
enabled connected after sync time and no success today -> due
enabled connected after sync time and success today -> not due
last success yesterday -> due
timezone uses APP_TIMEZONE local date
```

Test run behavior with fake Garmin client:

```text
due auto-sync calls existing sync service with days=35
success records last_auto_attempt_at
success records last_auto_success_at
success stores saved/skipped/warning counts
failure records last_auto_attempt_at
failure records sanitized last_auto_error
failure does not mark last_auto_success_at
second auto-sync same day is skipped
manual sync remains callable
stats/recovery endpoints do not run auto-sync
```

Test no secret leakage:

```text
settings response does not contain token path/token values
logs do not include password/token from fake exception
backup export does not include garmin_sync_settings if excluded by design
```

If scheduler loop is tested:

```text
startup creates background task
shutdown cancels background task
loop catches exceptions and continues
```

But avoid fragile async timing tests. Prefer direct service tests.

---

## Frontend checks

```bash
cd frontend
npm run typecheck
npm run build
```

Manual frontend checks:

```text
Settings loads when Garmin disconnected
Auto-sync section visible
Toggle enabled and save
Change time and save
Change sync_days and save, if UI supports it
Invalid time prevented or backend error shown
Manual Sync 35 days still works
Status refresh updates last success/attempt
Mobile layout ok
```

---

## Backend checks

```bash
python -m unittest discover -s tests
```

---

## Manual smoke

Real Home Assistant / add-on:

```text
Open Settings
Connect Garmin if needed
Enable Auto-sync Garmin daily
Set sync time earlier than current local time for testing
Wait for scheduler interval or trigger service manually in dev
Confirm logs show garmin.auto_sync.start
Confirm Settings shows last automatic success
Open /garmin and verify latest metric date updated
Open Current Workout and verify Garmin recovery card updated
Restart add-on
Confirm auto-sync setting persisted
Confirm it does not sync again if success already happened today
Press manual Sync 35 days and confirm it still works
Disable Auto-sync
Restart add-on
Confirm no auto-sync runs
```

Local/dev shortcut:

```text
GARMIN_AUTO_SYNC_CHECK_INTERVAL_SECONDS=300
APP_TIMEZONE=Europe/Uzhgorod
```

---

## Acceptance criteria

- Settings has an Auto-sync Garmin daily switch.
- Auto-sync is disabled by default.
- User can enable/disable auto-sync.
- Backend persists auto-sync setting.
- Backend automatically syncs at most once per local day when enabled and connected.
- Auto-sync uses the same Garmin sync logic as manual Sync 35 days.
- Manual Sync 35 days still works.
- No Garmin API call happens during page rendering.
- No credentials/tokens are stored in DB/backups/frontend/logs.
- Last attempt/success/error/result are visible in Settings.
- Auto-sync survives app restart.
- Auto-sync does not duplicate rows.
- Auto-sync does not run repeatedly on failures.
- Backend tests pass.
- Frontend typecheck/build pass.
