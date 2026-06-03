# Changelog

All notable changes to this project.

## Unreleased - 2026-06-04

### Changed
- Updated application logic: `app/main.py` — minor fixes and logging improvements.
- Templates updated: `app/templates/edit_workout.html`, `app/templates/history.html`, `app/templates/index.html`, `app/templates/workout.html` — UI tweaks and cleanup.
- Local database updated: `data/training.db` — schema/data changes.

### Notes
- These are pending/local changes to be included in the next release (0.1.4).


## 0.1.4 - 2026-06-03

### Changed
- chore: update templates, application logic, and config (364e2bb) — UI and logic tweaks; updated local DB. Affected: `app/main.py`, several templates, `config.yaml`, `data/training.db`.
- chore: update index template (c70bad5) — minor layout and content tweaks to the main index template. Affected: `app/templates/index.html`.
- refactor(template): remove duplicate 'Same' set button from edit_workout (5d40ef9) — simplified the edit workout UI by removing a redundant button. Affected: `app/templates/edit_workout.html`.
- Logger update (74ef2c8) — improved logging behavior. Affected: `app/main.py`, `data/training.db`.

### Notes
- These changes include UI tweaks, logging improvements, and a small database update.

---

Generated from commits since version 0.1.3.
