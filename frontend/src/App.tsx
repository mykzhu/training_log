import { lazy, Suspense, useEffect, useState } from "react";

import BackupPage from "./pages/BackupPage";
import CurrentWorkoutPage from "./pages/CurrentWorkoutPage";
import HistoryPage from "./pages/HistoryPage";
import SettingsPage from "./pages/SettingsPage";

const ExerciseStatsPage = lazy(() => import("./pages/ExerciseStatsPage"));
const StatsPage = lazy(() => import("./pages/StatsPage"));

type PageKey =
  | "current"
  | "history"
  | "stats"
  | "exercise-stats"
  | "backup"
  | "settings";

const pages: Array<{ key: PageKey; label: string }> = [
  { key: "current", label: "Current" },
  { key: "history", label: "History" },
  { key: "stats", label: "Stats" },
  { key: "backup", label: "Backup" },
  { key: "settings", label: "Settings" },
];

const historyNavItems: Array<{
  key: string;
  label: string;
  page: PageKey;
  path: string;
}> = [
  { key: "current", label: "Current", page: "current", path: "/" },
  { key: "stats", label: "Stats", page: "stats", path: "/stats" },
  { key: "backup", label: "Backup", page: "backup", path: "/backup" },
  { key: "settings", label: "Settings", page: "settings", path: "/settings" },
];

function pageFromPath(pathname: string): PageKey {
  if (/^\/exercises\/\d+\/stats\/?$/.test(pathname)) {
    return "exercise-stats";
  }
  if (pathname.startsWith("/history") || pathname.startsWith("/workouts/")) {
    return "history";
  }
  if (pathname.startsWith("/stats")) {
    return "stats";
  }
  if (pathname.startsWith("/backup")) {
    return "backup";
  }
  if (pathname.startsWith("/settings")) {
    return "settings";
  }

  return "current";
}

function pathForPage(page: PageKey): string {
  if (page === "current") {
    return "/";
  }
  if (page === "exercise-stats") {
    return "/stats";
  }

  return `/${page}`;
}

function workoutIdFromPath(pathname: string): number | null {
  const match = pathname.match(/^\/workouts\/(\d+)/);
  return match ? Number(match[1]) : null;
}

function exerciseStatsIdFromPath(pathname: string): number | null {
  const match = pathname.match(/^\/exercises\/(\d+)\/stats\/?$/);
  return match ? Number(match[1]) : null;
}

function workoutEditModeFromPath(pathname: string): boolean {
  return /^\/workouts\/\d+\/edit\/?$/.test(pathname);
}

export default function App() {
  const [activePage, setActivePage] = useState<PageKey>(() =>
    pageFromPath(window.location.pathname),
  );
  const [initialWorkoutId, setInitialWorkoutId] = useState<number | null>(() =>
    workoutIdFromPath(window.location.pathname),
  );
  const [initialWorkoutEditMode, setInitialWorkoutEditMode] = useState(() =>
    workoutEditModeFromPath(window.location.pathname),
  );
  const [exerciseStatsId, setExerciseStatsId] = useState<number | null>(() =>
    exerciseStatsIdFromPath(window.location.pathname),
  );

  useEffect(() => {
    function syncFromPath() {
      setActivePage(pageFromPath(window.location.pathname));
      setInitialWorkoutId(workoutIdFromPath(window.location.pathname));
      setInitialWorkoutEditMode(workoutEditModeFromPath(window.location.pathname));
      setExerciseStatsId(exerciseStatsIdFromPath(window.location.pathname));
    }

    window.addEventListener("popstate", syncFromPath);
    return () => window.removeEventListener("popstate", syncFromPath);
  }, []);

  function navigate(page: PageKey, path = pathForPage(page)) {
    setActivePage(page);
    setInitialWorkoutId(null);
    setInitialWorkoutEditMode(false);
    setExerciseStatsId(null);
    window.history.pushState(null, "", path);
  }

  const isHistoryList = activePage === "history" && initialWorkoutId === null;
  const isReadonlyWorkout =
    activePage === "history" &&
    initialWorkoutId !== null &&
    !initialWorkoutEditMode;
  const isEditWorkout =
    activePage === "history" &&
    initialWorkoutId !== null &&
    initialWorkoutEditMode;
  const isBackupPage = activePage === "backup";
  const isExerciseStats = activePage === "exercise-stats";
  const headerTitle = isHistoryList
    ? "History"
    : isReadonlyWorkout
      ? `Workout #${initialWorkoutId}`
      : isEditWorkout
        ? `Edit Workout #${initialWorkoutId}`
        : isBackupPage
          ? "Backup"
          : isExerciseStats
            ? "Exercise stats"
            : "Training Log";
  const headerSubtitle = isHistoryList
    ? "Last 30 workouts"
    : isReadonlyWorkout || isEditWorkout
      ? null
      : isBackupPage
        ? "Export, restore, or reset training history"
        : isExerciseStats
          ? "Stats"
          : pages.find((page) => page.key === activePage)?.label;
  const navItems = isHistoryList
    ? historyNavItems
    : pages.map((page) => ({
        key: page.key,
        label: page.label,
        page: page.key,
        path: pathForPage(page.key),
      }));

  const navActivePage = activePage === "exercise-stats" ? "stats" : activePage;

  return (
    <main className={`app-shell app-shell-${activePage}`}>
      <header className="app-header">
        <div>
          <h1>{headerTitle}</h1>
          {headerSubtitle && (
            <p className="muted active-label">{headerSubtitle}</p>
          )}
        </div>
        <nav className="tabs" aria-label="Main navigation">
          {navItems.map((item) => (
            <button
              className={item.page === navActivePage ? "tab tab-active" : "tab"}
              key={item.key}
              onClick={() => navigate(item.page, item.path)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      {activePage === "current" && <CurrentWorkoutPage />}
      {activePage === "history" && (
        <HistoryPage
          initialEditMode={initialWorkoutEditMode}
          initialWorkoutId={initialWorkoutId}
        />
      )}
      {activePage === "stats" && (
        <Suspense fallback={<section className="panel">Loading</section>}>
          <StatsPage />
        </Suspense>
      )}
      {activePage === "exercise-stats" && exerciseStatsId !== null && (
        <Suspense fallback={<section className="panel">Loading</section>}>
          <ExerciseStatsPage exerciseId={exerciseStatsId} />
        </Suspense>
      )}
      {activePage === "backup" && <BackupPage />}
      {activePage === "settings" && <SettingsPage />}
    </main>
  );
}
