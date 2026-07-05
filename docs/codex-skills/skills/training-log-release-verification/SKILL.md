---
name: training-log-release-verification
description: Use this before releasing Training Log. It verifies tests, frontend build, Docker build, changelog, version, docs, smoke tests, and known release blockers.
---

# Training Log Release Verification Skill

## When to use

Use before:

```text
version bump
release commit
tagging release
telling user it is release-ready
```

## Release checklist

### 1. Version metadata

Check:

```text
config.yaml
CHANGELOG.md
docs/CODEX_PLAN.md
```

Expected:

```text
config.yaml version matches release target
CHANGELOG has release section
CODEX_PLAN marks completed phases accurately
```

Do not claim release-ready if version and changelog disagree.

### 2. Backend tests

Run:

```bash
python -m unittest discover -s tests
```

Report exact result.

### 3. Frontend checks

Run:

```bash
cd frontend
npm run typecheck
npm run build
cd ..
```

If lint exists:

```bash
cd frontend
npm run lint
cd ..
```

### 4. Docker build

Run:

```bash
docker build -t training-log:<version> .
```

### 5. API/OpenAPI consistency

If backend schema changed:

```text
docs/openapi.json updated
frontend generated types updated
TypeScript build passes
```

### 6. Backup/restore

If data schema or backup changed:

```text
backup export works
restore works
old backups tested
no credentials/raw diagnostics leak
```

### 7. Manual smoke tests

Navigation:

```text
Current visible on /current
History visible on /history
Stats visible on /stats
Garmin visible on /garmin
Backup visible on /backup
Settings visible on /settings
active item highlighted
```

Settings:

```text
sections collapsed by default
Garmin settings expandable
auto-sync state visible
```

Active workout:

```text
start workout
add first exercise on phone viewport
no scroll jump
RPE auto-saves
Back pain auto-saves
finish workout
```

Edit workout:

```text
open from History
make changes
Unsaved changes appears
Save workout
refresh confirms persistence
```

Stats:

```text
charts render
date axes consistent
training load metrics render
empty states safe
```

Garmin:

```text
range buttons work
manual sync button works
no redundant Settings link
no sync on render
```

Home Assistant:

```text
open add-on through ingress
refresh deep link
assets load
API calls succeed
```

## Verdict format

Use:

```text
Verdict: release-ready / not release-ready / code OK but verification missing

Passed:
- ...

Failed:
- ...

Not verified:
- ...

Required before release:
- ...
```

## Hard blockers

Do not approve release if:

```text
backend tests fail
frontend build fails
Docker build fails
version mismatch
changelog missing
migration/restore broken
credentials leak
app crashes on normal page
```
