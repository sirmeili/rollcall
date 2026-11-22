import type { ShoppingList, ShoppingListItem } from "#lib/api/shopping.ts";
import type { CatalogLink, Product } from "#lib/api/types.ts";
import { product } from "./fixtures.ts";

export const STORE = "https://store.example";

export function link(overrides: Partial<CatalogLink> = {}): CatalogLink {
  return {
    uuid: "jade",
    name: "Jade White",
    line: "PLA Basic",
    hexes: ["F5F5F0"],
    bambu_code: "10100",
    how: "tag",
    in_catalog: true,
    linked_by: null,
    linked_at: null,
    was_line: null,
    was_name: null,
    tag_link_exists: true,
    ...overrides,
  };
}

/** A low-stock item: `sealed` Sealed spools against `threshold`. */
export function lowItem(
  id: number,
  name: string,
  threshold: number,
  sealed: number,
  overrides: Partial<Product> = {},
): ShoppingListItem {
  const spools = threshold - sealed + 1;
  return {
    product: product({ id, display_name: name, low_stock_threshold: threshold, ...overrides }),
    to_buy: spools,
    reasons: [{ kind: "low_stock", spools, sealed, threshold }],
  };
}

export function shoppingList(overrides: Partial<ShoppingList> = {}): ShoppingList {
  return { lines: [], not_in_catalog: [], store_address: STORE, ...overrides };
}
