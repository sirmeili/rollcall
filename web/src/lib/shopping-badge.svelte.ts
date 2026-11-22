/** The count of open suggestions, shown on the Shopping list link. The layout refreshes it on
 * every page change, and the Shopping list page updates it after each change it makes. */

import { suggestionCount } from "#lib/api/shopping.ts";

export class ShoppingBadge {
  count = $state(0);

  async refresh(): Promise<void> {
    try {
      this.count = await suggestionCount();
    } catch {
      // The badge is a hint; a failed refresh keeps the last count.
    }
  }
}

export const shoppingBadge = new ShoppingBadge();
