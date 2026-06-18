import { useEffect, useMemo, useRef, useState } from "react";

import { getBackup, resetBackupData, restoreBackup } from "../api/backup";
import type { BackupPayload } from "../api/backup";

export default function BackupPage() {
  const [backupPayload, setBackupPayload] = useState<BackupPayload | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  function beginAction() {
    setPending(true);
    setError(null);
    setMessage(null);
  }

  async function downloadBackup() {
    beginAction();

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

  async function restoreSelectedBackup() {
    if (!selectedFile) {
      setError("Choose a JSON backup first.");
      return;
    }

    if (
      !window.confirm(
        "Restore this backup and replace the current database?",
      )
    ) {
      return;
    }

    beginAction();

    try {
      const text = await selectedFile.text();
      const payload = JSON.parse(text) as BackupPayload;
      const response = await restoreBackup(payload);

      await loadBackupSummary();
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      setMessage(`Restore complete · ${response.counts.workouts} workouts`);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Restore failed.");
    } finally {
      setPending(false);
    }
  }

  async function resetData() {
    if (
      !window.confirm(
        "Reset the whole database? This cannot be undone unless you have a backup.",
      )
    ) {
      return;
    }

    beginAction();

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

  return (
    <section className="page-stack backup-page">
      {error && <div className="error-banner">{error}</div>}
      {message && <div className="success-banner">{message}</div>}

      <section className="panel backup-summary-card">
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
          JSON is best for full backup because it preserves IDs and links between
          workouts, exercises, and sets.
        </p>
        <button
          className="backup-action-button backup-export-button"
          disabled={pending}
          onClick={downloadBackup}
          type="button"
        >
          Download JSON backup
        </button>
      </section>

      <section className="panel backup-card">
        <h2>Restore</h2>
        <p className="backup-warning">
          Restore replaces the current database with the uploaded backup.
        </p>
        <input
          accept="application/json,.json"
          aria-label="Choose JSON backup"
          disabled={pending}
          onChange={(event) => {
            setSelectedFile(event.target.files?.[0] ?? null);
            setError(null);
            setMessage(null);
          }}
          ref={fileInputRef}
          type="file"
        />
        <button
          className="danger-button backup-action-button"
          disabled={pending || !selectedFile}
          onClick={restoreSelectedBackup}
          type="button"
        >
          Restore JSON backup
        </button>
      </section>

      <section className="panel backup-card">
        <h2>Reset database</h2>
        <p className="backup-warning">
          This deletes all workouts, sets, and custom exercises, then recreates
          the default exercise list.
        </p>
        <button
          className="danger-button backup-action-button"
          disabled={pending}
          onClick={resetData}
          type="button"
        >
          Reset database
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
