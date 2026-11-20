/** The Requests list's tabs, status filter and empty states. */

import type { RequestStatus, RequestTab } from "#lib/api/requests.ts";
import { STATUS_LABELS } from "#lib/requests/labels.ts";

export const TABS: { value: RequestTab; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "closed", label: "Closed" },
];

/** Where a request is finished with: the Closed tab. Every other status is open. */
export const CLOSED_STATUSES: RequestStatus[] = ["picked_up", "rejected", "cancelled"];

/** The statuses the Active tab holds, which Editors and Admins filter by, in pipeline order. */
export const OPEN_STATUSES = (Object.keys(STATUS_LABELS) as RequestStatus[]).filter(
  (status) => !CLOSED_STATUSES.includes(status),
);

export const SORT_TEXT: Record<RequestTab, string> = {
  active: "Most urgent first, then by needed-by date, then oldest first",
  closed: "Most recently closed first",
};

/** The status filter with one status turned on or off, kept in pipeline order. */
export function toggleStatus(chosen: RequestStatus[], status: RequestStatus): RequestStatus[] {
  const next = chosen.includes(status) ? chosen.filter((s) => s !== status) : [...chosen, status];
  return OPEN_STATUSES.filter((s) => next.includes(s));
}

export interface EmptyState {
  heading: string;
  text: string;
  /** Offer New request in the empty state. */
  offerNew: boolean;
}

export interface EmptyContext {
  tab: RequestTab;
  /** An Editor or Admin, who sees everyone's requests. */
  seesAll: boolean;
  canSubmit: boolean;
  /** A status filter or Only mine is on. */
  filtered: boolean;
}

/** What an empty tab says. */
export function emptyState({ tab, seesAll, canSubmit, filtered }: EmptyContext): EmptyState {
  if (filtered && tab === "active") {
    return {
      heading: "No matching requests",
      text: "Pick other statuses or turn off Only mine to see more.",
      offerNew: false,
    };
  }
  const everyone = seesAll && !filtered;
  if (tab === "closed") {
    return everyone
      ? {
          heading: "No closed requests",
          text: "Requests show up here once they're picked up, rejected or cancelled.",
          offerNew: false,
        }
      : {
          heading: "You don't have any closed requests",
          text: "Your requests show up here once they're picked up, rejected or cancelled.",
          offerNew: false,
        };
  }
  if (seesAll) {
    return {
      heading: "No active requests",
      text: canSubmit
        ? "Requests from everyone with the Requester permission show up here until they close. Start one yourself with New request."
        : "Requests from everyone with the Requester permission show up here until they close.",
      offerNew: canSubmit,
    };
  }
  return {
    heading: "You don't have any active requests",
    text: canSubmit
      ? "Ask for something to be printed: add a model file or link, pick filament, and say when you need it."
      : "You can no longer submit print requests. Your finished ones are on the Closed tab.",
    offerNew: canSubmit,
  };
}
