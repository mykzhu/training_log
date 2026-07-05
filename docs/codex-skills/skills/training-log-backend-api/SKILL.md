---
name: training-log-backend-api
description: Use this when changing Training Log FastAPI backend, schemas, repositories, migrations, OpenAPI, or generated frontend API types.
---

# Training Log Backend/API Skill

## When to use

Use this for changes in:

```text
app/
tests/
docs/openapi.json
frontend generated API/types
```

Especially:

```text
app/services/
app/repositories/
app/schemas.py
app/config.py
app/main.py
app/services/backup_service.py
```

## Backend rules

### API changes must be additive when possible

Prefer adding new response fields over changing existing field meanings.

If response schemas change:

```text
1. update Pydantic schemas
2. update OpenAPI
3. update generated frontend types if used
4. update frontend usage
5. add tests
```

### Validate inputs

Reject invalid values early.

For PATCH endpoints:

```text
- reject explicit null unless null is a meaningful value
- reject empty payload if it does nothing
- validate ranges
- validate time format
```

### Async safety

Never call blocking sync code directly inside async route/background task.

Use:

```python
await asyncio.to_thread(blocking_func, arg1, arg2)
```

or make the full path async.

### Timezone safety

Use app-local date/time.

Prefer existing date service / APP_TIMEZONE.

Do not use naive `datetime.now()` for user-visible app dates unless existing code pattern says it is local.

### Config safety

Environment parsing must not crash import.

Use safe helper:

```python
def int_env(name: str, default: int, minimum: int | None = None) -> int:
    ...
```

### Tests

For backend changes, add or update tests in:

```text
tests/
```

Default command:

```bash
python -m unittest discover -s tests
```

## Migration rules

When adding DB columns/tables:

```text
- migration is idempotent
- existing DB upgrades cleanly
- new installs work
- tests cover upgrade/empty DB if possible
```

Do not store credentials in backups.

Do not expose Garmin tokens/passwords in API responses.

## OpenAPI / generated types

If `docs/openapi.json` is part of repo, keep it in sync.

Codex must inspect existing scripts before inventing commands.

Possible commands:

```bash
python -m app.scripts.generate_openapi
npm run generate-api
```

If no generator exists, update using repo's current pattern.

## Output

Report:

```text
Backend files changed
API fields added/changed
Migration impact
Backup/restore impact
Tests run
Frontend type impact
```
