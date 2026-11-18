/** Who may do what with print requests (ADR-0017). Requester is a permission on top of a
 * role and never passes a role check. The API enforces the same rules. */

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
