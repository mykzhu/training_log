# Changelog

All notable changes to this project.

## 0.1.4 - 2026-06-04

### Added
- Add `CHANGELOG.md` to track release notes. (011c1c2)

### Changed
- Update templates and application logic (364e2bb, fc177d4, e6aaa0c) — UI and logic improvements across the app; refreshed changelog and final index tweaks. Affected: `app/main.py`, `app/templates/backup.html`, `app/templates/edit_workout.html`, `app/templates/history.html`, `app/templates/index.html`, `app/templates/workout.html`, `config.yaml`, `data/training.db`.
- Remove duplicate 'Same' set button in `edit_workout.html` (5d40ef9) — UI cleanup.
- Update index template (c70bad5) — minor layout and content tweaks.
- Logger update (74ef2c8) — improved logging behavior.
- Fix duration display in history (8041c85) — corrected formatting on history view.

### Notes
- This release contains UI improvements, logging fixes, and a small local DB update.

---

Commits included (newest first):
- e6aaa0c — chore: update index template and local DB; refresh changelog
- 8041c85 — Fixed duration
- fc177d4 — chore: update templates, main logic, and local DB; add changelog entry
- 011c1c2 — chore: add CHANGELOG.md (changes since 0.1.3)
- 5d40ef9 — refactor(template): remove duplicate 'Same' set button from edit_workout
- c70bad5 — chore: update index template
- 364e2bb — chore: update templates, application logic, and config
- 74ef2c8 — Logger update

Generated from commits since version 0.1.3.
