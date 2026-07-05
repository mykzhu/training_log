---
name: training-log-phase-executor
description: Use this when implementing a numbered Training Log phase from docs/CODEX_PLAN.md. It enforces small scoped changes, verification, docs updates, and no accidental scope creep.
---

# Training Log Phase Executor

## When to use

Use this skill when the task mentions:

- `Phase N`
- `CODEX_PLAN.md`
- implementing a planned Training Log phase
- "continue with next phase"
- "implement phase"
- release prep for a phase

## Project assumptions

This repository is the Home Assistant add-on / web app **Training Log**.

Expected structure:

```text
app/                         Backend FastAPI / services / schemas
frontend/src/                React frontend
tests/                       Python backend tests
docs/                        OpenAPI and Codex planning docs
config.yaml                  Home Assistant add-on metadata
CHANGELOG.md                 Release notes
docs/CODEX_PLAN.md           Active roadmap
```

## Mandatory workflow

### 1. Read the active plan first

Always inspect:

```text
docs/CODEX_PLAN.md
```

Find the exact phase requested.

Extract:

```text
- purpose
- target files
- implementation items
- acceptance criteria
- verification commands
```

Do not implement unrelated future phases.

### 2. Inspect existing code before editing

Before changing files, read the current implementation around every target area.

Examples:

```text
frontend/src/pages/CurrentWorkoutPage.tsx
frontend/src/pages/HistoryPage.tsx
frontend/src/pages/StatsPage.tsx
frontend/src/pages/SettingsPage.tsx
frontend/src/pages/GarminStatsPage.tsx
app/services/stats_service.py
app/schemas.py
tests/
```

Do not assume component names if search shows a different structure.

### 3. Keep changes phase-scoped

Each phase should be one logical commit.

Good commit examples:

```text
Phase 23: polish navigation, settings accordions, and Garmin stats controls
Phase 24: simplify active workout logging and auto-save session stats
Phase 28: add training load calculations and Stats integration
```

Avoid combining unrelated work.

### 4. Update docs only when appropriate

Update `docs/CODEX_PLAN.md` at the end of a phase:

```text
- mark the phase completed
- add any implementation notes
- do not mark later phases completed
```

For release phases, also update:

```text
CHANGELOG.md
config.yaml
docs/openapi.json, if API changed
frontend generated API/types, if API changed
```

### 5. Verification is mandatory

Run the commands listed in the phase plan when possible.

Default backend:

```bash
python -m unittest discover -s tests
```

Default frontend:

```bash
cd frontend
npm run typecheck
npm run build
cd ..
```

Default release build:

```bash
docker build -t training-log:<version> .
```

If a command cannot be run, report why.

## Output format to user

After finishing a phase, report:

```text
Implemented:
- ...

Changed files:
- ...

Verification:
- command: result
- command: result

Manual checks needed:
- ...

Risks / follow-ups:
- ...
```

## Do not

- Do not bump `config.yaml` version before release phase.
- Do not remove existing data compatibility.
- Do not alter Garmin credentials/auth behavior unless the phase explicitly says so.
- Do not add new libraries unless clearly necessary and justified.
- Do not delete Codex docs.
