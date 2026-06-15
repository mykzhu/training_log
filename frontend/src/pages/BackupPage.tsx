import { useState } from "react";

import { getBackup, resetBackupData } from "../api/backup";

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
      </section>
    </section>
  );
}
