# Changelog

All notable changes to this project.

## 1.0.0 - 2026-06-18

Training Log 1.0.0 is a major application rewrite. The legacy server-rendered interface has been replaced by a React frontend backed by a modular FastAPI API, with persistent workout drafts, configurable exercises, expanded analytics, safer backups, and improved Home Assistant deployment support.

### Highlights

* Complete React and TypeScript frontend built with Vite.
* Modular FastAPI backend with separate routes, services, repositories, schemas, and database initialization.
* Persistent current-workout drafts that survive page reloads and application restarts.
* Full exercise settings and weight-option management.
* Expanded workout history, analysis, progress charts, recommendations, and recovery insights.
* Backup schema version 3 with exercise configuration and weight options.
* New default exercise catalog for strength training.
* Automated backend, frontend, and Docker build checks.

### Added

* React-only application interface with Home Assistant ingress-compatible routing.
* REST APIs for:

  * Current workouts and persistent drafts.
  * Exercise management.
  * Workout history and workout editing.
  * Statistics and analytics.
  * Backup export, validation, restore, and reset.
* Persistent active-workout draft storage, including:

  * Exercises and sets.
  * Exercise order.
  * Set order.
  * Session RPE.
  * Lower-back pain.
  * Workout start time and duration.
* Exercise settings page with support for:

  * Creating and renaming exercises.
  * Activating and deactivating exercises.
  * Reordering exercises.
  * Assigning analysis profiles.
  * Configuring selectable weight options.
* Case-insensitive exercise-name validation.
* Profile-based exercise load analysis.
* New default exercise catalog:

  * Deadlift.
  * Squats.
  * DB Squats.
  * Bench Press.
  * 45-Degree Bench Press.
  * DB Bench Press.
  * Shoulder Press.
  * DB Shoulder Press.
  * EZ Biceps.
  * Triceps Pushdown.
  * Crunches.
* Expanded workout details with:

  * Total volume, sets, and repetitions.
  * Exercise-level volume.
  * Estimated one-repetition maximum.
  * Personal-record indicators.
  * Load, intensity, compound-load, and lower-back-load analysis.
* Recharts-based statistics dashboard.
* Normalized benchmark progress chart.
* Calendar and trend visualizations.
* Exercise progress and personal-record badges.
* Current-workout recommendations and recovery context.
* Backup schema version 3 containing:

  * Exercise active state.
  * Exercise ordering.
  * Analysis profile keys.
  * Exercise weight options.
* Validation for backup table IDs, relationships, exercise names, profiles, weights, sets, and repetitions.
* Compatibility when restoring older schema version 1 and 2 backups.
* SQLite indexes and query optimizations.
* Automated tests for APIs, repositories, services, backups, drafts, analytics, recovery, recommendations, and database behavior.
* GitHub Actions workflow for:

  * Backend tests.
  * Frontend dependency installation.
  * TypeScript checks.
  * Frontend production build.
  * Docker image build.
* Development, testing, Docker, and Home Assistant documentation.

### Changed

* Replaced the legacy Jinja/HTML frontend with a React and TypeScript single-page application.
* Reorganized the backend from a large application module into dedicated:

  * API route modules.
  * Repository modules.
  * Service modules.
  * Request and response schemas.
  * Database initialization and migration logic.
* Reworked workout creation, editing, set duplication, deletion, and ordering.
* Reworked workout history and workout-detail navigation.
* Improved the mobile and Home Assistant ingress experience.
* Updated the Docker build to compile the frontend in a dedicated Node.js build stage.
* Updated the frontend build stage to Node.js 22 LTS.
* Improved SQLite connection settings, indexes, foreign-key handling, ordering normalization, and query efficiency.
* Changed default exercise seeding to use explicit analysis-profile mappings.
* Changed the barbell squat profile key to `squats`.
* Changed the dumbbell squat profile key to `db_squats`.
* Improved load, intensity, recovery, readiness, recommendation, and progress calculations.
* Improved chart layouts, labels, responsive behavior, and visual consistency.
* Improved exercise and workout data hydration to reduce repeated database queries.
* Improved backup restore behavior to reset SQLite sequences correctly.
* Expanded runtime logging for database initialization, backup operations, and application behavior.
* Expanded ignored runtime files to cover SQLite databases, WAL/SHM files, tokens, frontend builds, and development artifacts.

### Fixed

* Fixed exercise weight seeding so every active default exercise receives selectable weights.
* Fixed the `Squats` profile and default-weight key mismatch.
* Fixed case-insensitive duplicate exercise handling.
* Fixed workout exercise and set ordering consistency.
* Fixed active-workout draft consistency after exercise settings changes.
* Fixed backup consistency after exercise activation, removal, or reordering.
* Fixed destructive backup validation by validating payloads before replacing existing data.
* Fixed workout mutation and deletion correctness.
* Fixed workout-detail navigation and history-page behavior.
* Fixed history-card and history-header layout regressions.
* Fixed session metadata type handling.
* Fixed several analytics, chart, and normalized benchmark calculation issues.
* Fixed SQLite query-count and performance regressions.

### Removed

* Removed the legacy server-rendered templates.
* Removed the tracked runtime SQLite database from the repository.
* Removed the old default exercise catalog.
* Removed Goblet Squat from the default exercise list and profile catalog.
* Removed direct coupling between page rendering and database operations in the main application module.

### Upgrade Notes

* Change the Home Assistant add-on version in `config.yaml` to `1.0.0`.
* Create a backup before upgrading from `0.2.0`.
* Backup schema version 3 includes exercise settings and selectable weights.
* Older schema version 1 and 2 backups remain accepted, but converting important production backups to schema version 3 before restore is recommended.
* Existing databases keep their current exercise records during normal startup.
* The new default exercise catalog is applied to fresh databases and database resets.
* Rebuild the Home Assistant add-on image after deploying the new source.
* Verify exercise settings and selectable weights after restoring an older backup.


---

## 0.2.0 - 2026-06-09

### Added
- Recommendation engine: next-workout recommendations and recovery context (`dee9d5d`, `1f83d80`).
- History-based readiness scoring to inform recommendations (`80f91b3`).

### Changed
- Improved recommendation engine algorithms and tuning (`26b0b3b`).

### Notes
- Bumped version in `config.yaml` to `0.2.0`.

---

## 0.1.9 - 2026-06-08

### Added
- Load calendar data and calendar heatmap support (`fdad62d`).

### Changed
- Add X/Y values to line charts to improve plotting (`5809f2e`).
- Improve scatter-plot rendering and data processing (`9836f88`).

### Fixed
- Fix heatmap loading bug (`e16367a`).

### Notes
- Bumped version in `config.yaml` to `0.1.9`.

---

## 0.1.8 - 2026-06-06

### Changed
- Refine `stats2` layout and UI across templates; improve sparkbar and chart rendering, markers, and axis notes.
- `app/main.py`: tweak server-side chart helpers and stats aggregation (e.g. `build_stats2_charts`, `build_line_chart_series`, `build_sparkbar`) and improve PR/e1RM calculations.
- Template/UI tweaks across `app/templates/*` and local DB migration/seeding (`data/training.db`).

### Notes
- Bumped version in `config.yaml` to `0.1.8`.

---

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
