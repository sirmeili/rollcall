/** The words the Settings page's Catalog card uses for a sync's status and results. */

import type { SyncStatus } from "#lib/api/catalog.ts";
import { shortDate } from "#lib/format.ts";

/** "v2026.11.15", or "—" before the first sync. */
export function versionText(version: string | null): string {
  return version ? `v${version}` : "—";
}

/** Why the last attempt failed. */
function reason(status: SyncStatus): string {
  return status.last_reason ?? "unknown error";
}

/** The note under the last attempt's time: "Not modified", "Updated", "Failed: …". */
export function attemptNote(status: SyncStatus): string {
  switch (status.last_result) {
    case "updated":
      return "Updated";
    case "not_modified":
      return "Not modified";
    case "failed":
      return `Failed: ${reason(status)}`;
    default:
      return "";
  }
}

/** The warning for a failed last attempt, saying which copy is still in use; null when the
 * last attempt worked. */
export function failureText(status: SyncStatus, now: Date = new Date()): string | null {
  if (status.last_result !== "failed") return null;
  const kept = status.last_success_at
    ? `Keeping the copy from ${shortDate(status.last_success_at, now)}.`
    : "There is no copy yet.";
  return `Last attempt failed: ${reason(status)}. ${kept}`;
}

/** What Refresh now found, given the status before and after it. */
export function refreshText(
  before: SyncStatus | null,
  after: SyncStatus,
  now = new Date(),
): string {
  switch (after.last_result) {
    case "updated":
      return `Updated to ${versionText(after.dataset_version)}: ${after.colors} catalog colors.`;
    case "not_modified": {
      const since = before?.last_success_at;
      return since ? `Up to date. Nothing new since ${shortDate(since, now)}.` : "Up to date.";
    }
    default:
      return `Sync failed: ${reason(after)}.`;
  }
}

export type CatalogSchedule = "off" | "daily" | "weekly";

export const SCHEDULES: readonly { value: CatalogSchedule; label: string }[] = [
  { value: "off", label: "Off" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
];

/** What the chosen schedule does. */
export function scheduleHelp(schedule: string): string {
  if (schedule === "off") return "The catalog stays as it is until you press Refresh now.";
  return `From api.openfilamentdatabase.org, ${schedule === "weekly" ? "once a week" : "once a day"}.`;
}

/** "10.0" from the server shows as "10". */
export function cutoffValue(value: string | null): string {
  const n = Number(value);
  return value === null || value.trim() === "" || Number.isNaN(n) ? (value ?? "") : String(n);
}

/** The problem with a typed cutoff, or null when it can be saved. */
export function cutoffProblem(text: string): string | null {
  const n = Number(text);
  return text.trim() === "" || !(n >= 0.5 && n <= 50)
    ? "Similarity cutoff: enter a number from 0.5 to 50."
    : null;
}
