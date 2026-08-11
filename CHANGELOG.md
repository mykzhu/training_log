# Changelog

All notable changes to this project.

## Unreleased

## 1.8.0 - 2026-08-11

### Added

* Added manual duration entry for duration-only exercises with readable values such as `30 sec` and `1:15`.
* Added a local live timer for duration-only exercise sets with Stop & Add logging.

## 1.7.0 - 2026-07-09

### Added

* Added exercise measurement metadata so weighted lifts, bodyweight reps, and loaded carries can be displayed and analyzed correctly.
* Added measurement controls to Settings for exercise type and rep unit.
* Added kg-volume, bodyweight-rep, duration, load-score, and back-stress derived metrics to workout details and Stats.
* Added load-first Stats charts, including training load versus back feedback and back-stress by exercise.
* Added data-quality notes for bodyweight work, zero-kg weighted sets, missing feedback, and incomplete Garmin data.
* Added a compact Log tab for line-by-line application logs.
* Added delete flows for workouts, exercises, analysis profiles, and Garmin metrics where supported.

### Changed

* Renamed visible volume analytics to kg volume where bodyweight work is excluded.
* Garmin readiness now marks partial current-day metrics separately from complete historical metrics.
* Backup schema version is now 8 and includes exercise measurement settings while restoring older backups without those fields.
* Set timestamps remain audit-only and are not used for rest-time, density, or tempo analytics.

### Fixed

* Fixed analytics for Crunches and other bodyweight-rep exercises so they contribute to load and back-stress without fake kg volume.
* Fixed exercise stats display for bodyweight and loaded-carry exercises.
* Removed the duplicate Log page title and reduced log row bulk.

## 1.6.0 - 2026-07-09

### Added

* Added per-exercise set option settings for default, minimum, maximum, and step values for weight and reps.
* Added generated per-exercise weight and reps choices to active workout and edit workout flows.
* Added folded-by-default Settings cards for Analysis Types and Exercises and Weights.

### Changed

* Backup schema version is now 7 and includes per-exercise set option settings.
* Settings now keeps dense analysis and exercise configuration hidden until the user expands a card.

### Fixed

* Fixed Crunches and other high-rep exercises so saved reps ranges appear in new workouts.
* Fixed reps option stepping so a step of 5 produces clean increments such as 20, 25, 30, and 35.

## 1.5.0 - 2026-07-06

### Improved

* Added recent-change insight cards to the Stats dashboard.
* Improved the volume trend tooltip with date, volume, sets, and reps.
* Added a load vs lower-back pain scatter chart with cautious, non-medical wording.
* Made training-load labels easier to understand with Short-term load, Long-term load, and Freshness labels before ATL/CTL/TSB terms.
* Improved analytics empty states and mobile behavior for new Stats sections.

### Notes

* This release keeps the single dark theme.
* No light theme, theme switcher, chart color refactor, backend sparkbar API change, or Active Workout redesign was added.

## 1.3.2 - 2026-07-06

### Fixed

* Fixed Stats overview sparklines by parsing the exact glyph set emitted by the backend sparkbar builder.
* Fixed current workout metadata PATCH behavior so omitted fields no longer clear existing RPE or lower back pain values.
* Hardened completed workout exercise and set numbering against duplicate position/set-number collisions.
* Renumbered completed workout exercise positions after deleting an exercise to keep ordering sequential.

## 1.3.1 - 2026-07-06

### Changed

* Polished Stats dashboard layout, metric cards, training-load chart, and calculations panel.
* Improved Stats desktop layout and mobile readability.
* Standardized ATL/CTL/TSB colors and metric status labels.

### Fixed

* Fixed misleading top-card labels and visuals for 7-day load, strength intensity, and consistency.
* Removed duplicate ATL/CTL/TSB rows from the Training load card.

## 1.3.0 - 2026-07-05

Training Log 1.3.0 focuses on cleaner Settings and navigation, simplified workout logging on mobile, unified edit-workout saving, improved Stats chart formatting, visual metric cards, and app-native training-load metrics.

### Added

* Added training-load calculations: ATL, CTL, TSB, AC ratio, monotony, and training strain.
* Added visual metric cards with progress bars, range bars, and sparklines on the Stats page.
* Added grouped Training load status chart for ATL, CTL, and TSB.
* Added advanced Calculations panel for training-load metrics.

### Changed

* Settings sections now start collapsed with summary text for Garmin, Analysis Types, and Exercises and Weights.
* Top navigation now keeps the same visible items on every page and highlights the current page.
* Active Workout now adds existing exercises only and links users to Settings for exercise creation.
* Active Workout session RPE and Back pain now auto-save when changed and show lightweight save status.
* Edit Workout now uses one page-level Save workout action with an Unsaved changes state.
* Current and Edit Workout delete controls now use the same compact `×` style.
* Stats charts now use consistent readable date labels and responsive mobile X-axis labels.

### Removed

* Removed redundant inline Settings link from Garmin stats controls.
* Removed inline exercise creation from active workout page.
* Removed separate Save workout info button from edit workout page.

### Fixed

* Preserved mobile scroll position when adding an exercise to an active workout.
* Fixed test monkeypatch cleanup for `asyncio.to_thread`.

## 1.2.0 - 2026-07-02

Training Log 1.2.0 is a Garmin recovery, Home Assistant ingress, and configuration release. It adds local Garmin metrics and readiness insights, automatic Garmin syncing, runtime-safe Home Assistant prefix handling, configurable Analysis Types, and a componentized Stats page. Backup schema support is extended for Analysis Types and normal backups no longer include Garmin raw diagnostics.

### Highlights

* Garmin daily metrics import with HRV, resting heart rate, stress, Body Battery, steps, local sync status, and Garmin Stats page.
* Garmin readiness adjustment in Next Workout recommendations using local persisted data only.
* Garmin auto-sync settings that can refresh recent metrics once per local day.
* Home Assistant ingress/toolbox prefix handling for deep links, API calls, and built assets.
* Configurable Analysis Types with custom load, compound, and back factors.
* Backup schema support for Analysis Types and Garmin daily metrics.
* Componentized global Stats page cards, charts, load calendar, and strength table.

### Added

* Runtime frontend base-path detection for Home Assistant ingress URLs.
* React Router basename support for prefixed Home Assistant routes.
* API request prefixing so `/api/v1/...` calls work under Home Assistant ingress.
* Backend prefix stripping for configured `APP_URL_PREFIX` and `/api/hassio_ingress/<token>`.
* `APP_URL_PREFIX` environment setting.
* Garmin daily metrics database storage and sync endpoints.
* Garmin Stats page with readiness signals, freshness status, baselines, trend charts, and readiness impact.
* Garmin recovery snapshot on Current Workout.
* Detailed Garmin readiness adjustment block in Next Workout.
* Shared Garmin insights helpers used by stats and readiness.
* Garmin auto-sync settings table and `GET/PATCH /api/v1/garmin/auto-sync`.
* Background Garmin auto-sync scheduler with once-per-local-day guard.
* Settings UI for Garmin auto-sync enable/disable, sync time, sync range, last attempt, last success, last result, and last error.
* DB-backed Analysis Types table.
* Settings UI for adding/editing/deactivating Analysis Types.
* Exercise assignment support for active custom Analysis Types.
* Backup schema support for Analysis Types.
* Componentized global Stats page cards, charts, load calendar, and strength table.

### Changed

* Vite build now uses relative asset base for prefixed deployment.
* Garmin stats and recovery views use application-local dates via `APP_TIMEZONE`.
* Garmin readiness and Garmin Stats share date, baseline, and freshness interpretation helpers.
* Exercise load calculations use DB-backed Analysis Type factors.
* Manual and automatic Garmin sync use the same sync logic.
* Auto-sync settings are operational config and are intentionally excluded from backups.
* Normal backup export no longer includes Garmin raw diagnostics.
* Settings now fold the Garmin and Analysis Types sections by default-open native disclosure panels.

### Fixed

* Fixed Home Assistant ingress deep-link refreshes.
* Fixed Home Assistant toolbox/Open Web UI prefixed asset/API behavior.
* Fixed Garmin stats/readiness inconsistencies caused by separate interpretation paths.
* Fixed stale historical Garmin data being displayed but not scored as current recovery.
* Fixed Garmin auto-sync blocking the event loop.
* Fixed `next_eligible_at` after failed auto-sync attempts.
* Fixed unsafe explicit `null` values in Garmin auto-sync updates.
* Fixed invalid auto-sync interval env parsing.
* Fixed long Garmin auto-sync errors from breaking the Settings layout.
* Fixed manual sync copy so it matches the configured sync range.
* Fixed normal backup export to exclude Garmin raw diagnostics.

### Upgrade Notes

* Change the Home Assistant add-on version in `config.yaml` to `1.2.0`.
* Create a backup before upgrading from `1.0.1`.
* Backup schema version 6 includes Analysis Types and excludes Garmin raw diagnostics from normal exports.
* Restore remains compatible with older schema versions 4 and 5 backups that include Garmin diagnostics.
* Auto-sync settings are intentionally not exported in backups and remain disabled after restore.
* Rebuild the Home Assistant add-on image after deploying the new source.

## 1.0.1 - 2026-06-18

Training Log 1.0.1 is a UI polish and Home Assistant usability release. It keeps the React/FastAPI architecture from 1.0.0, restores the practical legacy workout workflow where it was faster to use, and fixes mobile layout issues found during phone testing.

### Added

* Read-only workout detail view with the legacy summary layout, analysis card, exercise tables, personal-record badges, estimated 1RM values, and full-width Edit/Delete actions.
* Post-workout recommendation card on read-only workout details.
* Legacy-style edit workout page at `/workouts/{id}/edit` with old-style workout info, add-exercise controls, editable set rows, save buttons, navigation, and danger zone.
* Legacy-style active workout page with old-style stats, analysis, session status, add-exercise controls, inline exercise creation, set tables, and full-width Finish workout action.
* Active-workout support for creating a new exercise while logging a workout.

### Changed

* Workout history now separates read-only and edit flows:

  * Clicking a workout title opens the read-only summary.
  * Clicking Edit opens the dedicated editable route.
* Restored the old visual density for active, read-only, and edit workout pages while keeping the newer React data model and APIs.
* Improved mobile grids so key metric cards remain two per row where useful:

  * Stats dashboard cards.
  * Stats summary cards.
  * Recovery context cards.
  * Next workout recommendation cards.
  * Active workout summary cards.
* Removed horizontal mobile scrolling from the Weekly exercise workload and Strength versus workload charts.
* Improved mobile layout for edit workout controls, exercise headers, set rows, save/delete actions, and navigation buttons.

### Fixed

* Fixed recovery context mobile gaps by rendering the metrics in one continuous grid instead of several three-item grids.
* Fixed chart overflow on mobile for weekly exercise workload and strength-versus-workload charts.
* Fixed edit workout mobile rows where selectors and action buttons could wrap into an awkward layout.
* Fixed active workout mobile summary and recovery cards collapsing to a single column too early.
* Fixed UI regressions from the 1.0.0 React rewrite where legacy workout pages were faster and clearer for phone use.

### Upgrade Notes

* Change the Home Assistant add-on version in `config.yaml` to `1.0.1`.
* Rebuild or update the Home Assistant add-on image after pulling this release.
* No database migration is required from `1.0.0`.
* Create a backup before upgrading, especially when updating the production Home Assistant add-on.

---

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
