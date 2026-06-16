import { useEffect, useMemo, useState } from "react";

import { getBackup, resetBackupData, restoreBackup } from "../api/backup";
import type { BackupPayload } from "../api/backup";

export default function BackupPage() {
  const [backupPayload, setBackupPayload] = useState<BackupPayload | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const counts = useMemo(() => {
    if (!backupPayload) {
      return {
        exercises: "—",
        workouts: "—",
        workout_exercises: "—",
        set_entries: "—",
      };
    }

    return {
      exercises: backupPayload.tables.exercises?.length ?? 0,
      workouts: backupPayload.tables.workouts?.length ?? 0,
      workout_exercises: backupPayload.tables.workout_exercises?.length ?? 0,
      set_entries: backupPayload.tables.set_entries?.length ?? 0,
    };
  }, [backupPayload]);

  async function loadBackupSummary() {
    const payload = await getBackup();
    setBackupPayload(payload);
  }

  useEffect(() => {
    loadBackupSummary().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Failed to load backup.");
    });
  }, []);

  async function downloadBackup() {
    setPending(true);
    setError(null);
    try {
      const payload = await getBackup();
      setBackupPayload(payload);
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `training-log-backup-${payload.exported_at.replace(/:/g, "")}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setMessage("Backup ready");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Action failed.");
    } finally {
      setPending(false);
    }
  }

  async function resetData() {
    if (!window.confirm("Reset all training data?")) {
      return;
    }

    setPending(true);
    setError(null);
    try {
      const response = await resetBackupData();
      await loadBackupSummary();
      setMessage(`Reset complete · ${response.counts.exercises} exercises`);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Action failed.");
    } finally {
      setPending(false);
    }
  }

  async function importBackup(file: File | null) {
    if (!file) {
      return;
    }

    setPending(true);
    setError(null);
    try {
      const text = await file.text();
      const payload = JSON.parse(text) as BackupPayload;
      const response = await restoreBackup(payload);
      await loadBackupSummary();
      setMessage(`Restore complete · ${response.counts.workouts} workouts`);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Restore failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="page-stack">
      {error && <div className="error-banner">{error}</div>}
      {message && <div className="success-banner">{message}</div>}

      <section className="panel">
        <h2>Current database</h2>
        <div className="stat-grid backup-counts">
          <Stat label="exercises" value={counts.exercises} />
          <Stat label="workouts" value={counts.workouts} />
          <Stat label="entries" value={counts.workout_exercises} />
          <Stat label="sets" value={counts.set_entries} />
        </div>
      </section>

      <section className="panel backup-card">
        <h2>Export</h2>
        <p className="muted">
          JSON is best for full backup because it preserves IDs and links.
        </p>
        <button
          className="primary-button"
          disabled={pending}
          onClick={downloadBackup}
          type="button"
        >
          Download JSON
        </button>
      </section>

      <section className="panel backup-card">
        <h2>Restore</h2>
        <p className="muted">
          Restore replaces the current database with the uploaded backup.
        </p>
        <label className="file-control">
          Restore JSON backup
          <input
            accept="application/json,.json"
            disabled={pending}
            onChange={(event) => importBackup(event.target.files?.[0] ?? null)}
            type="file"
          />
        </label>
      </section>

      <section className="panel backup-card">
        <h2>Reset database</h2>
        <p className="muted">
          This deletes all workouts, sets, and custom exercises, then recreates
          the default exercise list.
        </p>
        <button
          className="secondary-button danger-text"
          disabled={pending}
          onClick={resetData}
          type="button"
        >
          Reset Data
        </button>
      </section>
    </section>
  );
}

type StatProps = {
  label: string;
  value: number | string;
};

function Stat({ label, value }: StatProps) {
  return (
    <div className="stat-card">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}
