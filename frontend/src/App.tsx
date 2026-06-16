import { useEffect, useState } from "react";

import BackupPage from "./pages/BackupPage";
import CurrentWorkoutPage from "./pages/CurrentWorkoutPage";
import HistoryPage from "./pages/HistoryPage";
import StatsPage from "./pages/StatsPage";

type PageKey = "current" | "history" | "stats" | "backup";

const pages: Array<{ key: PageKey; label: string }> = [
  { key: "current", label: "Current" },
  { key: "history", label: "History" },
  { key: "stats", label: "Stats" },
  { key: "backup", label: "Backup" },
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

  function navigate(page: PageKey) {
    setActivePage(page);
    setInitialWorkoutId(null);
    window.history.pushState(null, "", pathForPage(page));
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1>Training Log</h1>
          <p className="muted active-label">
            {pages.find((page) => page.key === activePage)?.label}
          </p>
        </div>
        <nav className="tabs" aria-label="Main navigation">
          {pages.map((page) => (
            <button
              className={page.key === activePage ? "tab tab-active" : "tab"}
              key={page.key}
              onClick={() => navigate(page.key)}
              type="button"
            >
              {page.label}
            </button>
          ))}
        </nav>
      </header>

      {activePage === "current" && <CurrentWorkoutPage />}
      {activePage === "history" && <HistoryPage initialWorkoutId={initialWorkoutId} />}
      {activePage === "stats" && <StatsPage />}
      {activePage === "backup" && <BackupPage />}
    </main>
  );
}
