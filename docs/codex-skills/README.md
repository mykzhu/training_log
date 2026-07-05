# Training Log — Codex Skills Pack

This pack contains portable Markdown `SKILL.md` files for recurring Training Log development tasks.

Recommended repo placement:

```text
docs/codex-skills/
  training-log-phase-executor/SKILL.md
  training-log-code-reviewer/SKILL.md
  training-log-frontend-ux/SKILL.md
  training-log-backend-api/SKILL.md
  training-log-stats-training-load/SKILL.md
  training-log-garmin-safety/SKILL.md
  training-log-backup-restore/SKILL.md
  training-log-home-assistant-addon/SKILL.md
  training-log-release-verification/SKILL.md
```

Use them in Codex by attaching/pasting the relevant skill before a task, or by storing them wherever your Codex environment loads custom skills from.

These skills assume the current project structure around:

```text
app/
frontend/src/
tests/
docs/
config.yaml
CHANGELOG.md
docs/CODEX_PLAN.md
```

General rule for every skill:

```text
Do not silently change runtime behavior.
Read the relevant files first.
Make small phase-based commits.
Run tests/builds.
Update docs when behavior changes.
```
