import { useState } from "react";

import { getBackup, resetBackupData, restoreBackup } from "../api/backup";
import type { BackupPayload } from "../api/backup";

export default function BackupPage() {
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function downloadBackup() {
    setPending(true);
    setError(null);
    try {
      const payload = await getBackup();
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
      <section className="panel action-panel">
        <button
          className="primary-button"
          disabled={pending}
          onClick={downloadBackup}
          type="button"
        >
          Download JSON
        </button>
        <button
          className="secondary-button danger-text"
          disabled={pending}
          onClick={resetData}
          type="button"
        >
          Reset Data
        </button>
        <label className="file-control">
          Import JSON
          <input
            accept="application/json,.json"
            disabled={pending}
            onChange={(event) => importBackup(event.target.files?.[0] ?? null)}
            type="file"
          />
        </label>
      </section>
    </section>
  );
}
