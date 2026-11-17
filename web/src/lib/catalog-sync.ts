/** The words the Settings page's Catalog card uses for each source's sync status, and
 * for Refresh now's results. */

import type { SourceStatus, SyncStatus } from "#lib/api/catalog.ts";
import { shortDate } from "#lib/format.ts";

export type SourceKey = "ofdb" | "bambustudio";

/** The catalog's two sources, as the status block names them. */
export const SOURCES: readonly { key: SourceKey; name: string; host: string }[] = [
  { key: "ofdb", name: "Open Filament Database", host: "api.openfilamentdatabase.org" },
  { key: "bambustudio", name: "BambuStudio color codes", host: "raw.githubusercontent.com" },
];

/** "v2026.11.15", or "—" before the first sync. */
export function versionText(version: string | null): string {
  return version ? `v${version}` : "—";
}

/** Why the last attempt failed. */
function reason(status: SourceStatus): string {
  return status.last_reason ?? "unknown error";
}

/** The note under the last attempt's time: "Not modified", "Updated", "Failed: …". */
export function attemptNote(status: SourceStatus): string {
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
export function failureText(status: SourceStatus, now: Date = new Date()): string | null {
  if (status.last_result !== "failed") return null;
  const kept = status.last_success_at
    ? `Keeping the copy from ${shortDate(status.last_success_at, now)}.`
    : "There is no copy yet.";
  return `Last attempt failed: ${reason(status)}. ${kept}`;
}

/** What Refresh now found in both sources. */
export function refreshText(after: SyncStatus): string {
  const { ofdb, bambustudio } = after;
  if (ofdb.last_result === "not_modified" && bambustudio.last_result === "not_modified") {
    return "Up to date. Nothing new in either source.";
  }
  const parts: string[] = [];
  if (ofdb.last_result === "updated") {
    parts.push(`Updated to ${versionText(ofdb.dataset_version)}: ${after.colors} catalog colors.`);
  } else if (ofdb.last_result === "failed") {
    parts.push(`OFDB sync failed: ${reason(ofdb)}.`);
  }
  if (bambustudio.last_result === "updated") {
    parts.push("Updated BambuStudio's color codes.");
  } else if (bambustudio.last_result === "failed") {
    parts.push(`BambuStudio sync failed: ${reason(bambustudio)}.`);
  }
  return parts.join(" ");
}

export type CatalogSchedule = "off" | "daily" | "weekly";

export const SCHEDULES: readonly { value: CatalogSchedule; label: string }[] = [
  { value: "off", label: "Off" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
];

/** What the chosen schedule does. */
export function scheduleHelp(schedule: string): string {
  if (schedule === "off") {
    return "The catalog and Bambu codes stay as they are until you press Refresh now.";
  }
  const sources =
    "From api.openfilamentdatabase.org and BambuStudio's color code list on GitHub (raw.githubusercontent.com)";
  return `${sources}, ${schedule === "weekly" ? "once a week" : "once a day"}.`;
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

export const STORE_ADDRESS_PROBLEM =
  "Enter an https address with no path, like https://us.store.bambulab.com";

/** A typed Store address as it is saved: trimmed, without one trailing slash. */
export function storeAddressValue(text: string): string {
  return text.trim().replace(/\/$/, "");
}

/** The problem with a typed Store address, or null when it can be saved: an https address
 * with a host and no path, query, fragment or user info. */
export function storeAddressProblem(text: string): string | null {
  const value = storeAddressValue(text);
  if (!/^https:\/\/[^/?#@\s]+$/.test(value)) return STORE_ADDRESS_PROBLEM;
  try {
    new URL(value);
  } catch {
    return STORE_ADDRESS_PROBLEM;
  }
  return null;
}
