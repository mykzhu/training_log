---
name: training-log-backup-restore
description: Use this when changing Training Log backup/export/restore, database schema versions, analysis profiles, Garmin metrics, or release compatibility.
---

# Training Log Backup and Restore Skill

## When to use

Use for changes in:

```text
app/services/backup_service.py
tests/test_backup_service.py
tests/test_api_backup.py
database migrations
schemas that affect exported data
analysis profiles
Garmin metrics
```

## Core rules

### Backups are compatibility contracts

A new version must restore older backups unless there is an explicit migration break.

When bumping backup schema:

```text
- update BACKUP_SCHEMA_VERSION
- update allowed restore schema versions
- add restore defaults for older schemas
- add tests for old schema restore
- add tests for new schema export
```

### Do not leak sensitive/debug data

Normal backups should not include:

```text
Garmin credentials
tokens
session cookies
raw auth state
large raw diagnostics
```

If raw fields exist in DB for compatibility, export only intended safe columns.

### Restore must be robust

Restore should handle:

```text
missing newer fields in old backups
extra older fields in older backups
empty arrays
null optional values
invalid required fields with clear error
```

### Schema versioning

When adding new export data:

```text
schema N+1 export includes it
schema N restore defaults it
tests cover both
```

Do not bump schema just for frontend-only UI changes.

## Garmin raw_diagnostics pattern

Preferred:

```text
DB insert columns can include raw_diagnostics.
Current backup export columns exclude raw_diagnostics.
Restore from older backup with raw_diagnostics accepts and stores/defaults safely.
Restore from current backup defaults raw_diagnostics to {} internally if DB requires it.
```

## Tests to add/update

```text
new schema export contains expected keys
new schema export excludes sensitive/debug keys
old schema restore still works
current schema restore validates required fields
missing optional fields default correctly
invalid backup is rejected cleanly
API backup endpoint returns expected schema version
```

## Verification

Run:

```bash
python -m unittest discover -s tests
```

Manual:

```text
export backup
inspect JSON
restore into empty DB
open app
verify data present
```
