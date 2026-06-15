import { jsonBody, requestJson } from "./client";

export type BackupPayload = {
  app: string;
  schema_version: number;
  exported_at: string;
  tables: Record<string, unknown[]>;
};

export function getBackup() {
  return requestJson<BackupPayload>("/api/v1/backup");
}

export function restoreBackup(payload: BackupPayload) {
  return requestJson<{ restored: boolean; counts: Record<string, number> }>(
    "/api/v1/backup/import",
    {
      method: "POST",
      body: jsonBody(payload),
    },
  );
}

export function resetBackupData() {
  return requestJson<{ reset: boolean; counts: Record<string, number> }>(
    "/api/v1/backup/reset",
    { method: "POST" },
  );
}
