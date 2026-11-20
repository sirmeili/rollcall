/** Words for print requests on the Requests pages. */

import type { HistoryEntry, ModelSource, Priority, RequestStatus } from "#lib/api/requests.ts";
import { calendarDay } from "#lib/format.ts";

/** In the order the form offers them. */
export const PRIORITIES: Priority[] = ["no_rush", "normal", "urgent"];

export const PRIORITY_LABELS: Record<Priority, string> = {
  urgent: "Urgent",
  normal: "Normal",
  no_rush: "No rush",
};

/** The longest note or reason a move takes, once trimmed. */
export const NOTE_MAX = 500;

export const STATUS_LABELS: Record<RequestStatus, string> = {
  submitted: "Submitted",
  approved: "Approved",
  waiting_on_filament: "Waiting on Filament",
  queued: "Queued",
  printing: "Printing",
  done: "Done",
  picked_up: "Picked Up",
  rejected: "Rejected",
  cancelled: "Cancelled",
  failed: "Failed",
};

/** A move's button and dialog words, by the status it leads to. */
export interface MoveWords {
  /** The button, and the dialog's confirm button. */
  action: string;
  /** The dialog's heading. */
  question: string;
  /** The history entry's title. */
  done: string;
  /** The dialog's button that closes it without moving, when "Cancel" would be unclear. */
  dismiss?: string;
}

const MOVE_WORDS: Partial<Record<RequestStatus, MoveWords>> = {
  approved: { action: "Approve", question: "Approve this request?", done: "Approved" },
  rejected: { action: "Reject", question: "Reject this request?", done: "Rejected" },
  queued: { action: "Queue", question: "Queue this request?", done: "Queued" },
  printing: {
    action: "Start printing",
    question: "Start printing this request?",
    done: "Started printing",
  },
  done: { action: "Mark Done", question: "Mark this request Done?", done: "Marked Done" },
  failed: { action: "Mark Failed", question: "Mark this request Failed?", done: "Marked Failed" },
  picked_up: {
    action: "Mark Picked Up",
    question: "Mark this request Picked Up?",
    done: "Marked Picked Up",
  },
  cancelled: {
    action: "Cancel request",
    question: "Cancel this request?",
    done: "Cancelled",
    dismiss: "Keep request",
  },
};

/** A move out of Failed to Queued, or to Waiting on Filament when its filament is short:
 * another attempt of the same request. */
const REPRINT: MoveWords = {
  action: "Reprint",
  question: "Reprint this request?",
  done: "Reprinted",
};

/** Whether a move from one status to another is a Reprint, wherever it lands. */
export function isReprint(from: RequestStatus | undefined, to: RequestStatus): boolean {
  return from === "failed" && (to === "queued" || to === "waiting_on_filament");
}

/** A move's words, by the status it leads to and, for a Reprint, the one it leaves. */
export function moveWords(to: RequestStatus, from?: RequestStatus): MoveWords {
  if (isReprint(from, to)) return REPRINT;
  return (
    MOVE_WORDS[to] ?? {
      action: `Move to ${STATUS_LABELS[to]}`,
      question: `Move this request to ${STATUS_LABELS[to]}?`,
      done: `Moved to ${STATUS_LABELS[to]}`,
    }
  );
}

/** Where a request stops going ahead: never the main next step. */
const STOPS: RequestStatus[] = ["rejected", "cancelled", "failed"];

/** The main next step among the moves offered, for the primary button; null if none. */
export function mainMove(moves: { to_status: RequestStatus }[]): RequestStatus | null {
  return moves.find((move) => !STOPS.includes(move.to_status))?.to_status ?? null;
}

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

/** Status changes are titled by the status moved to instead (moveWords). */
const HISTORY_VERBS: Record<Exclude<HistoryEntry["kind"], "status_changed">, string> = {
  submitted: "Submitted",
  edited: "Edited",
  priority_changed: "Priority changed",
  photo_added: "Photo added",
  photo_removed: "Photo removed",
};

function statusLabel(value: string | null): string {
  return STATUS_LABELS[value as RequestStatus];
}

/** "Edited by sam", "Approved by frank", "Queued automatically"; an entry by a token has no
 * one to name. */
export function historyTitle(entry: HistoryEntry): string {
  const verb =
    entry.kind === "status_changed"
      ? moveWords(entry.to_value as RequestStatus, entry.from_value as RequestStatus).done
      : HISTORY_VERBS[entry.kind];
  if (entry.automatic) return `${verb} automatically`;
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
  if (entry.kind === "status_changed") {
    return `${statusLabel(entry.from_value)} → ${statusLabel(entry.to_value)}`;
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
