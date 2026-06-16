import { lazy, Suspense, useEffect, useState } from "react";

import BackupPage from "./pages/BackupPage";
import CurrentWorkoutPage from "./pages/CurrentWorkoutPage";
import HistoryPage from "./pages/HistoryPage";

const StatsPage = lazy(() => import("./pages/StatsPage"));

type PageKey = "current" | "history" | "stats" | "backup";

const pages: Array<{ key: PageKey; label: string }> = [
  { key: "current", label: "Current" },
  { key: "history", label: "History" },
  { key: "stats", label: "Stats" },
  { key: "backup", label: "Backup" },
];

const historyNavItems: Array<{
  key: string;
  label: string;
  page: PageKey;
  path: string;
}> = [
  { key: "current", label: "Current", page: "current", path: "/" },
  { key: "stats", label: "Stats", page: "stats", path: "/stats" },
  { key: "stats2", label: "Stats 2", page: "stats", path: "/stats2" },
  { key: "backup", label: "Backup", page: "backup", path: "/backup" },
];

function pageFromPath(pathname: string): PageKey {
  if (pathname.startsWith("/history") || pathname.startsWith("/workouts/")) {
    return "history";
  }
  if (pathname.startsWith("/stats")) {
    return "stats";
  }
  if (pathname.startsWith("/backup")) {
    return "backup";
  }

  return "current";
}

function pathForPage(page: PageKey): string {
  if (page === "current") {
    return "/";
  }

  return `/${page}`;
}

function workoutIdFromPath(pathname: string): number | null {
  const match = pathname.match(/^\/workouts\/(\d+)/);
  return match ? Number(match[1]) : null;
}

export default function App() {
  const [activePage, setActivePage] = useState<PageKey>(() =>
    pageFromPath(window.location.pathname),
  );
  const [initialWorkoutId, setInitialWorkoutId] = useState<number | null>(() =>
    workoutIdFromPath(window.location.pathname),
  );

  useEffect(() => {
    function syncFromPath() {
      setActivePage(pageFromPath(window.location.pathname));
      setInitialWorkoutId(workoutIdFromPath(window.location.pathname));
    }

    window.addEventListener("popstate", syncFromPath);
    return () => window.removeEventListener("popstate", syncFromPath);
  }, []);

  function navigate(page: PageKey, path = pathForPage(page)) {
    setActivePage(page);
    setInitialWorkoutId(null);
    window.history.pushState(null, "", path);
  }

  const isHistoryList = activePage === "history" && initialWorkoutId === null;
  const headerTitle = isHistoryList ? "History" : "Training Log";
  const headerSubtitle = isHistoryList
    ? "Last 30 workouts"
    : pages.find((page) => page.key === activePage)?.label;
  const navItems = isHistoryList
    ? historyNavItems
    : pages.map((page) => ({
        key: page.key,
        label: page.label,
        page: page.key,
        path: pathForPage(page.key),
      }));

  return (
    <main className={`app-shell app-shell-${activePage}`}>
      <header className="app-header">
        <div>
          <h1>{headerTitle}</h1>
          <p className="muted active-label">{headerSubtitle}</p>
        </div>
        <nav className="tabs" aria-label="Main navigation">
          {navItems.map((item) => (
            <button
              className={item.page === activePage ? "tab tab-active" : "tab"}
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
      {activePage === "history" && <HistoryPage initialWorkoutId={initialWorkoutId} />}
      {activePage === "stats" && (
        <Suspense fallback={<section className="panel">Loading</section>}>
          <StatsPage />
        </Suspense>
      )}
      {activePage === "backup" && <BackupPage />}
    </main>
  );
}
