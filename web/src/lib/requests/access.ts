/** Who may do what with print requests (ADR-0017). Requester is a permission on top of a
 * role and never passes a role check. The API enforces the same rules. */

import type { PrintRequest } from "#lib/api/requests.ts";
import type { Me } from "#lib/api/types.ts";
import { allows } from "#lib/roles.ts";

/** Editors and Admins see every request and change priorities. */
export function seesEveryRequest(user: Me | null | undefined): boolean {
  return allows(user?.role, "editor");
}

/** The Requests pages are for Editors and Admins, Requesters, and anyone who has made a
 * request (who keeps read-only access to their own after Requester is turned off). */
export function canOpenRequests(user: Me | null | undefined): boolean {
  return !!user && (seesEveryRequest(user) || user.requester || user.has_requests);
}

/** Submitting and editing need Requester, whatever the role. */
export function canSubmit(user: Me | null | undefined): boolean {
  return !!user?.requester;
}

/** Why this user can't edit a request they can open; null when the reason needs no saying
 * (they can edit it). */
export function whyNoEdit(user: Me | null | undefined, request: PrintRequest): string | null {
  if (request.can_edit) return null;
  if (user?.id !== request.requester.id)
    return "Only the person who asked for this request can edit it.";
  if (!user.requester) return "You can no longer edit this request: you're no longer a Requester.";
  return "This request can no longer be edited.";
}
