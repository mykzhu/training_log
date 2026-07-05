---
name: training-log-garmin-safety
description: Use this when changing Garmin sync, Garmin stats, readiness integration, auto-sync, Garmin settings, or Garmin backup behavior in Training Log.
---

# Training Log Garmin Safety Skill

## When to use

Use for:

```text
Garmin sync
Garmin auto-sync
Garmin stats page
Garmin readiness/current workout integration
Garmin settings UI
Garmin backup/restore data
```

## Safety rules

### Never expose secrets

Do not expose or back up:

```text
Garmin username
Garmin password
tokens
session cookies
raw auth state
```

### Raw diagnostics

Raw diagnostics may exist in DB for debugging, but normal backups should not export them unless explicitly designed.

Current preferred behavior:

```text
DB can keep raw_diagnostics for compatibility/debug.
Backup schema should exclude raw_diagnostics from normal export.
Restore from old backups that contain raw_diagnostics should remain compatible.
```

### No sync on page render

Do not call Garmin network sync just because a page renders.

Allowed sync triggers:

```text
Manual Sync button
Configured auto-sync background task
Explicit connect/MFA flow
```

### Async safety

Garmin sync is blocking unless proven otherwise.

In async tasks/routes use:

```python
await asyncio.to_thread(garmin_service.sync, days)
```

### Auto-sync rules

Default behavior:

```text
disabled by default
runs at most once per local app day
runs after configured local time
skips if Garmin disconnected
records last_attempt_at
records last_success_at
records last_error
does not retry repeatedly on same day after failed attempt unless design changes explicitly
```

### Timezone

Display and calculate auto-sync in app-local timezone.

UI should mention local time.

## Garmin stats UI

Do not add redundant Settings links inside `/garmin` action row if global nav already has Settings.

Keep:

```text
range buttons
manual sync button
status/error info
```

## Tests

When touching Garmin sync:

```text
connected vs disconnected
success records attempt/success/result
failure records attempt/error
same-day guard
next_eligible_at after success today
next_eligible_at after failed attempt today
invalid settings validation
explicit null rejected in PATCH
blocking sync offloaded to thread
```

## Do not

- Do not sync during React render.
- Do not back up credentials.
- Do not leak raw diagnostics in schema 6+ backups.
- Do not make sync-days unbounded.
- Do not crash import on bad env var.
