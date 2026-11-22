import type { ShoppingListItem } from "#lib/api/shopping.ts";
import type { WholeRange } from "#lib/format.ts";
import { MAX_SPOOLS } from "#lib/shopping-add.ts";

/** "3 need · 1 on order" */
export function needText(item: ShoppingListItem): string {
  return `${item.need} need · ${item.on_order} on order`;
}

/** Ordered asks how many, starting from to buy; at least 1 for an item fully ordered. */
export function orderedDefault(item: ShoppingListItem): number {
  return Math.max(item.to_buy, 1);
}

/** What an item's on order can be set to. */
export const ON_ORDER: WholeRange = { label: "On order", min: 0, max: MAX_SPOOLS };

/** A group's items still to buy, then those fully ordered, which show under On order. */
export function byOrdered(items: ShoppingListItem[]): {
  toBuy: ShoppingListItem[];
  ordered: ShoppingListItem[];
} {
  return {
    toBuy: items.filter((item) => item.to_buy > 0),
    ordered: items.filter((item) => item.to_buy === 0),
  };
}
