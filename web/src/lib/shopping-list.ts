import type { ShoppingList, ShoppingListItem, ShoppingReason } from "#lib/api/shopping.ts";
import type { Product } from "#lib/api/types.ts";
import { storeSearchUrl } from "#lib/catalog.ts";

/** "1 spool", "3 spools" */
export function spoolsText(spools: number): string {
  return `${spools} ${spools === 1 ? "spool" : "spools"}`;
}

/** Why an item is on the list: "Low stock: 1 sealed, threshold 2 · 2 spools". */
export function reasonText(reason: ShoppingReason): string {
  return `Low stock: ${reason.sealed} sealed, threshold ${reason.threshold} · ${spoolsText(reason.spools)}`;
}

/** The store's search for the product's catalog color, only when it has a Bambu code. */
export function findInStore(storeAddress: string, product: Product): string | null {
  const code = product.catalog_link?.bambu_code;
  // The search is by the Bambu code alone, so the line and color name are not needed.
  return code ? storeSearchUrl(storeAddress, "", "", code) : null;
}

/** A group of the shopping list as the page shows it: a filament line, or Not in the
 * catalog. */
export interface ShoppingGroup {
  key: string;
  name: string;
  toBuy: number;
  items: ShoppingListItem[];
  /** Show each product's filament type (Not in the catalog). */
  showType: boolean;
}

/** The filament lines in the order served, then Not in the catalog when it has items. */
export function shoppingGroups(list: ShoppingList): ShoppingGroup[] {
  const groups: ShoppingGroup[] = list.lines.map((line, i) => ({
    key: `line-${i}`,
    name: line.name,
    toBuy: line.to_buy,
    items: line.items,
    showType: false,
  }));
  if (list.not_in_catalog.length > 0) {
    groups.push({
      key: "not-in-catalog",
      name: "Not in the catalog",
      toBuy: list.not_in_catalog.reduce((sum, item) => sum + item.to_buy, 0),
      items: list.not_in_catalog,
      showType: true,
    });
  }
  return groups;
}
