/** Words for print requests on the Requests pages. */

import type { HistoryEntry, ModelSource, Priority } from "#lib/api/requests.ts";
import { calendarDay } from "#lib/format.ts";

/** In the order the form offers them. */
export const PRIORITIES: Priority[] = ["no_rush", "normal", "urgent"];

export const PRIORITY_LABELS: Record<Priority, string> = {
  urgent: "Urgent",
  normal: "Normal",
  no_rush: "No rush",
};

/** Where a request's model is, as the list says it. */
export const MODEL_TEXT: Record<ModelSource, string> = {
  file: "File",
  link: "Link",
  both: "File and link",
  notes: "Notes only",
};

const DAY_MS = 24 * 60 * 60 * 1000;

function dayNumber(ymd: string): number {
  const [year, month, day] = ymd.split("-").map(Number);
  return Date.UTC(year, month - 1, day) / DAY_MS;
}

/** "today", "tomorrow", "in 3 days", "yesterday", "3 days ago": from one calendar day
 * (YYYY-MM-DD) to another. */
export function relativeDay(ymd: string, today: string): string {
  const days = dayNumber(ymd) - dayNumber(today);
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  if (days === -1) return "yesterday";
  return days > 0 ? `in ${days} days` : `${-days} days ago`;
}

/** relativeDay for a moment, by the calendar of the time zone in use. */
export function relativeTime(iso: string, now: Date = new Date()): string {
  return relativeDay(calendarDay(new Date(iso)), calendarDay(now));
}

/** "Nov 24" for a needed-by date (a calendar day, not a moment). */
export function neededByDate(ymd: string): string {
  return new Date(`${ymd}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** "a", "a and b", "a, b and c" */
export function listText(words: string[]): string {
  if (words.length < 2) return words.join("");
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

const FIELD_NAMES: Record<string, string> = {
  title: "title",
  quantity: "quantity",
  needed_by: "needed by",
  priority: "priority",
  link: "link",
  notes: "notes",
  file: "file",
  filament: "filament",
};

const HISTORY_VERBS: Record<HistoryEntry["kind"], string> = {
  submitted: "Submitted",
  edited: "Edited",
  priority_changed: "Priority changed",
};

/** "Edited by sam"; an entry by the admin token has no one to name. */
export function historyTitle(entry: HistoryEntry): string {
  const verb = HISTORY_VERBS[entry.kind];
  return entry.username ? `${verb} by ${entry.username}` : verb;
}

/** "Changed notes and needed by", "Normal → Urgent"; null when there is nothing more. */
export function historyDetail(entry: HistoryEntry): string | null {
  if (entry.kind === "edited" && entry.fields?.length) {
    return `Changed ${listText(entry.fields.map((field) => FIELD_NAMES[field] ?? field))}`;
  }
  if (entry.kind === "priority_changed" && entry.from_value && entry.to_value) {
    const label = (value: string) => PRIORITY_LABELS[value as Priority] ?? value;
    return `${label(entry.from_value)} → ${label(entry.to_value)}`;
  }
  return null;
}

/** "18.6 MB", "740 KB" */
export function sizeText(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** "Similar in stock: A, B +2", "No similar color in stock"; null names a multi-color one,
 * which gets no comparison (as on the Catalog page). */
export function similarText(names: string[] | null, most = names?.length ?? 0): string {
  if (names === null) return "Multi-color: no comparison";
  if (names.length === 0) return "No similar color in stock";
  const more = names.length - most;
  return `Similar in stock: ${names.slice(0, most).join(", ")}${more > 0 ? ` +${more}` : ""}`;
}
