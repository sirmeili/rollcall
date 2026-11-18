/** The count of Submitted print requests, shown on the Requests link to Editors and Admins.
 * The layout refreshes it on every page change. */

import { submittedCount } from "#lib/api/requests.ts";

export class RequestsBadge {
  count = $state(0);

  async refresh(): Promise<void> {
    try {
      this.count = await submittedCount();
    } catch {
      // The badge is a hint; a failed refresh keeps the last count.
    }
  }

  clear(): void {
    this.count = 0;
  }
}

export const requestsBadge = new RequestsBadge();
