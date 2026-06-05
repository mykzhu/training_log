# Changelog

All notable changes to this project.

## 0.1.7 - 2026-06-05

### Added
- `app/templates/stats2.html` — new "Stats 2" analytics dashboard with dashboard sparkbars, area/line charts for volume/intensity/RPE/back pain, calendar heatmaps, scatter plot (volume vs back pain), exercise volume bars, and best-strength (e1RM) estimates.
- Server-side chart helpers in `app/main.py` (`build_stats2_charts`, `build_line_chart_series`, `build_sparkbar`, `build_calendar_heatmap`, `build_scatter_points`, `estimated_1rm`) to compute chart data for the template.

### Changed
- `app/main.py`: compute and expose additional stats (total volume, avg intensity, session RPE, back pain, PR detection) and refine workout analysis to support the new dashboard.
- `data/training.db`: local DB updates and migrations/seeding to ensure stats-related fields and default exercises exist.

### Notes
- Bumped version in `config.yaml` to `0.1.7`.

---

## 0.1.6 - 2026-06-05

### Added
- Add stats page and supporting routes/logic (6e88c7a) — new `app/templates/stats.html` and initial stats integration.

### Changed
- Refine stats UI and supporting logic (af5227d) — UI tweaks and logic adjustments for stats features.
- chore: ongoing stats improvements and local DB updates (7418751) — database updates to support stats data.

### Notes
- This release adds a stats page and finalizes related UI and DB changes.

---


## 0.1.5 - 2026-06-04

### Added
- `app/templates/_analysis_card.html` — new reusable analysis card component. (c5574e1)

### Changed
- feat(ui): UI tweaks across workout/index views to integrate analysis card and improve layout. (c5574e1)
- fix(workout): parse session metadata inputs as integers to ensure consistent types (1161626)

### Notes
- These changes add a small UI component and improve input handling for session metadata.

---

Commits included (newest first):
- 1161626 — fix(workout): parse session metadata as integers
- c5574e1 — feat(ui): add analysis card and tweak workout/index templates


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

