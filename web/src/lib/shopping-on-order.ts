import type { ShoppingListItem } from "#lib/api/shopping.ts";
import { MAX_SPOOLS } from "#lib/shopping-add.ts";

/** "3 need · 1 on order" */
export function needText(item: ShoppingListItem): string {
  return `${item.need} need · ${item.on_order} on order`;
}

/** Ordered asks how many, starting from to buy; at least 1 for an item fully ordered. */
export function orderedDefault(item: ShoppingListItem): number {
  return Math.max(item.to_buy, 1);
}

/** Why a number can't be on order, or null: a whole number, 0 to 999. */
export function onOrderProblem(spools: number | null): string | null {
  const whole = spools !== null && Number.isInteger(spools) && spools >= 0;
  return whole && spools <= MAX_SPOOLS ? null : `On order: a whole number, 0 to ${MAX_SPOOLS}.`;
}

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
