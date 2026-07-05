import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import {
  BrowserRouter,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";

import BackupPage from "./pages/BackupPage";
import CurrentWorkoutPage from "./pages/CurrentWorkoutPage";
import HistoryPage from "./pages/HistoryPage";
import NotFoundPage from "./pages/NotFoundPage";
import SettingsPage from "./pages/SettingsPage";
import { appBasePath } from "./utils/basePath";

const ExerciseStatsPage = lazy(() => import("./pages/ExerciseStatsPage"));
const GarminStatsPage = lazy(() => import("./pages/GarminStatsPage"));
const StatsPage = lazy(() => import("./pages/StatsPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

type PageKey =
  | "current"
  | "history"
  | "stats"
  | "exercise-stats"
  | "garmin"
  | "backup"
  | "settings";

type ShellPageKey = PageKey | "not-found";

type RouteInfo = {
  editMode?: boolean;
  page: ShellPageKey;
  workoutId?: number;
};

const pages: Array<{ key: PageKey; label: string }> = [
  { key: "current", label: "Current" },
  { key: "history", label: "History" },
  { key: "stats", label: "Stats" },
  { key: "garmin", label: "Garmin" },
  { key: "backup", label: "Backup" },
  { key: "settings", label: "Settings" },
];

function pathForPage(page: PageKey): string {
  if (page === "current") {
    return "/";
  }
  if (page === "exercise-stats") {
    return "/stats";
  }

  return `/${page}`;
}

function numericRouteParam(value: string | undefined) {
  if (!value) {
    return null;
  }

  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function routeInfoFromPath(pathname: string): RouteInfo {
  const cleanPath = pathname.replace(/\/$/, "") || "/";
  const editWorkoutMatch = cleanPath.match(/^\/workouts\/(\d+)\/edit$/);
  if (editWorkoutMatch) {
    return {
      editMode: true,
      page: "history",
      workoutId: Number(editWorkoutMatch[1]),
    };
  }

  const readonlyWorkoutMatch = cleanPath.match(/^\/workouts\/(\d+)$/);
  if (readonlyWorkoutMatch) {
    return {
      editMode: false,
      page: "history",
      workoutId: Number(readonlyWorkoutMatch[1]),
    };
  }

  if (cleanPath === "/") {
    return { page: "current" };
  }
  if (cleanPath === "/history") {
    return { page: "history" };
  }
  if (cleanPath === "/stats") {
    return { page: "stats" };
  }
  if (/^\/exercises\/\d+\/stats$/.test(cleanPath)) {
    return { page: "exercise-stats" };
  }
  if (cleanPath === "/garmin") {
    return { page: "garmin" };
  }
  if (cleanPath === "/backup") {
    return { page: "backup" };
  }
  if (cleanPath === "/settings") {
    return { page: "settings" };
  }

  return { page: "not-found" };
}

function LoadingPanel() {
  return <section className="panel">Loading</section>;
}

function WorkoutRoute({ initialEditMode }: { initialEditMode: boolean }) {
  const { workoutId } = useParams();
  const parsedWorkoutId = numericRouteParam(workoutId);

  if (parsedWorkoutId === null) {
    return <NotFoundPage />;
  }

  return (
    <HistoryPage
      initialEditMode={initialEditMode}
      initialWorkoutId={parsedWorkoutId}
    />
  );
}

function ExerciseStatsRoute() {
  const { exerciseId } = useParams();
  const parsedExerciseId = numericRouteParam(exerciseId);

  if (parsedExerciseId === null) {
    return <NotFoundPage />;
  }

  return <ExerciseStatsPage exerciseId={parsedExerciseId} />;
}

function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const routeInfo = routeInfoFromPath(location.pathname);
  const activePage = routeInfo.page;
  const workoutId = routeInfo.workoutId ?? null;
  const isHistoryList = activePage === "history" && workoutId === null;
  const isReadonlyWorkout =
    activePage === "history" && workoutId !== null && !routeInfo.editMode;
  const isEditWorkout =
    activePage === "history" && workoutId !== null && routeInfo.editMode;
  const isBackupPage = activePage === "backup";
  const isExerciseStats = activePage === "exercise-stats";
  const isNotFound = activePage === "not-found";
  const headerTitle = isHistoryList
    ? "History"
    : isReadonlyWorkout
      ? `Workout #${workoutId}`
      : isEditWorkout
        ? `Edit Workout #${workoutId}`
        : isBackupPage
          ? "Backup"
          : isExerciseStats
            ? "Exercise stats"
            : isNotFound
              ? "Not found"
              : "Training Log";
  const headerSubtitle = isHistoryList
    ? "Last 30 workouts"
    : isReadonlyWorkout || isEditWorkout || isNotFound
      ? null
      : isBackupPage
        ? "Export, restore, or reset training history"
        : isExerciseStats
          ? "Stats"
          : pages.find((page) => page.key === activePage)?.label;
  const navItems = pages.map((page) => ({
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
              onClick={() => navigate(item.path)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      <Suspense fallback={<LoadingPanel />}>
        <Routes>
          <Route path="/" element={<CurrentWorkoutPage />} />
          <Route
            path="/history"
            element={
              <HistoryPage initialEditMode={false} initialWorkoutId={null} />
            }
          />
          <Route
            path="/workouts/:workoutId"
            element={<WorkoutRoute initialEditMode={false} />}
          />
          <Route
            path="/workouts/:workoutId/edit"
            element={<WorkoutRoute initialEditMode />}
          />
          <Route path="/stats" element={<StatsPage />} />
          <Route
            path="/exercises/:exerciseId/stats"
            element={<ExerciseStatsRoute />}
          />
          <Route path="/garmin" element={<GarminStatsPage />} />
          <Route path="/backup" element={<BackupPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </main>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={appBasePath() || undefined}>
        <AppLayout />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
