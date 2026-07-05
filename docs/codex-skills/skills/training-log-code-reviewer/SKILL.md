---
name: training-log-code-reviewer
description: Use this for precise code review of Training Log changes. It focuses on bugs, UI regressions, data compatibility, Home Assistant add-on behavior, and release readiness.
---

# Training Log Code Reviewer

## When to use

Use this skill when asked to:

- recheck master
- review latest code
- review a phase implementation
- find bugs and UI gaps
- decide if release-ready
- compare latest changes against a previous commit

## Review priorities

Review in this order:

```text
1. Data safety and migrations
2. Backend correctness
3. API schema compatibility
4. Frontend behavior and mobile UX
5. Garmin sync safety
6. Backup/restore compatibility
7. Home Assistant ingress/add-on behavior
8. Tests and release metadata
9. Docs and changelog hygiene
```

## Mandatory checks

### Git / diff

Compare against the last known reviewed base.

Example:

```text
base: previous reviewed commit
head: master
```

Identify:

```text
- new commits
- changed files
- deleted files
- version changes
```

### Backend

Check:

```text
app/services/
app/repositories/
app/schemas.py
app/main.py
app/config.py
tests/
```

Look for:

```text
- blocking sync code inside async routes/background tasks
- missing input validation
- unsafe null handling
- timezone mistakes
- migration compatibility problems
- accidental credential/token exposure
- unbounded raw diagnostic data
- tests that monkeypatch globals without restore
```

### Frontend

Check:

```text
frontend/src/pages/
frontend/src/components/
frontend/src/styles.css
frontend generated API/types
```

Look for:

```text
- mobile layout crowding
- active navigation disappearing
- duplicate buttons or redundant links
- uncontrolled/controlled input bugs
- stale query cache after mutations
- missing error status
- save behavior mismatch
- page scroll jumps
```

### Backup / restore

Check:

```text
app/services/backup_service.py
tests/test_backup_service.py
tests/test_api_backup.py
```

Verify:

```text
- old backups still restore
- new backups do not leak raw diagnostics or credentials
- schema version bumps are intentional
- missing fields have safe defaults
```

### Release readiness

Check:

```text
config.yaml
CHANGELOG.md
docs/CODEX_PLAN.md
docs/openapi.json
```

Also check CI/status if available.

## Review output format

Use a direct verdict first:

```text
Verdict: release-ready / not release-ready / code OK but verification missing
```

Then:

```text
Blockers:
1. ...

Important non-blockers:
1. ...

Good fixes:
1. ...

Required before release:
1. ...

Suggested commit:
...
```

## Severity rules

### Blocker

Use blocker for:

```text
- data loss
- failed migration/restore
- event loop blocking in async path
- security/credential leak
- app crash on normal usage
- broken build/typecheck
- wrong version/release metadata
```

### Important non-blocker

Use for:

```text
- UI inconsistency
- missing error message
- poor mobile layout
- test hygiene risk
- docs inconsistency
```

### Nice-to-have

Use for:

```text
- refactor
- polish
- optional performance improvement
```

## Do not

- Do not assume tests passed if no CI status or logs exist.
- Do not invent files that were not inspected.
- Do not approve release if version/changelog/tests are missing.
- Do not ignore deleted docs.
