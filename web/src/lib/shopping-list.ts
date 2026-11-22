import type {
  ShoppingHistoryEntry,
  ShoppingList,
  ShoppingListItem,
  ShoppingReason,
} from "#lib/api/shopping.ts";
import type { Product } from "#lib/api/types.ts";
import { storeSearchUrl } from "#lib/catalog.ts";
import { dateTime } from "#lib/format.ts";

/** "1 spool", "3 spools" */
export function spoolsText(spools: number): string {
  return `${spools} ${spools === 1 ? "spool" : "spools"}`;
}

/** Why an item is on the list: "Low stock: 1 sealed, threshold 2 · 2 spools", "Added by
 * hand by frank · 1 spool". */
export function reasonText(reason: ShoppingReason): string {
  if (reason.kind === "hand") {
    const by = reason.by ? ` by ${reason.by}` : "";
    return `Added by hand${by} · ${spoolsText(reason.spools)}`;
  }
  return `Low stock: ${reason.sealed} sealed, threshold ${reason.threshold} · ${spoolsText(reason.spools)}`;
}

/** What a history entry records: "Added 2 spools by hand". */
export function historyText(entry: ShoppingHistoryEntry): string {
  const spools = spoolsText(entry.spools ?? 0);
  if (entry.action === "added_by_hand") return `Added ${spools} by hand`;
  if (entry.action === "removed_by_hand") return `Removed ${spools} added by hand`;
  const words = entry.action.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Who did it, when, and the on order after: "frank · Nov 21, 12:00 PM · 0 on order". */
export function historyWhen(entry: ShoppingHistoryEntry, now: Date = new Date()): string {
  const parts = [dateTime(entry.at, now), `${entry.on_order} on order`];
  return (entry.by ? [entry.by, ...parts] : parts).join(" · ");
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
