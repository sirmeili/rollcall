import { api } from "#lib/api/client.ts";
import type { Product } from "#lib/api/types.ts";

/** The product is low: buying `spools` takes its Sealed count above its threshold. */
export interface LowStockReason {
  kind: "low_stock";
  spools: number;
  sealed: number;
  threshold: number;
}

export type ShoppingReason = LowStockReason;

/** One product on the shopping list, with the reasons it is there. */
export interface ShoppingListItem {
  product: Product;
  to_buy: number;
  reasons: ShoppingReason[];
}

/** A filament line's items, from their products' catalog links. */
export interface ShoppingLine {
  name: string;
  /** The line's items' to buy, added up. */
  to_buy: number;
  /** By product name. */
  items: ShoppingListItem[];
}

export interface ShoppingList {
  /** By name. */
  lines: ShoppingLine[];
  /** Products with no catalog link, by name. */
  not_in_catalog: ShoppingListItem[];
  /** The store Find in store searches, without a trailing slash. */
  store_address: string;
}

/** The shopping list (every role). */
export function getShoppingList(): Promise<ShoppingList> {
  return api<ShoppingList>("/shopping-list");
}
