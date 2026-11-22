import type {
  HandReason,
  RequestReason,
  ShoppingHistoryEntry,
  ShoppingList,
  ShoppingListItem,
  Suggestion,
} from "#lib/api/shopping.ts";
import type { CatalogLink, Product } from "#lib/api/types.ts";
import { product } from "./fixtures.ts";

export const STORE = "https://store.example";

export const DEFAULT_SIZE = { grams: 1000, source: "default" } as const;

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
    need: spools,
    on_order: 0,
    reasons: [{ kind: "low_stock", spools, sealed, threshold }],
    size: DEFAULT_SIZE,
    history: [],
    dismissed_need: null,
    new_since_dismissal: null,
  };
}

export function shoppingList(overrides: Partial<ShoppingList> = {}): ShoppingList {
  return {
    suggestions: [],
    lines: [],
    not_in_catalog: [],
    store_address: STORE,
    dismissed: [],
    ...overrides,
  };
}

export function handReason(id: number, spools: number, by: string | null = "frank"): HandReason {
  return { kind: "hand", id, spools, by, at: "2026-11-21T12:00:00Z" };
}

/** An item on the list only for spools added by hand. */
export function handItem(
  id: number,
  name: string,
  reasons: HandReason[],
  overrides: Partial<Product> = {},
): ShoppingListItem {
  const need = reasons.reduce((sum, reason) => sum + reason.spools, 0);
  return {
    product: product({ id, display_name: name, low_stock_threshold: 0, ...overrides }),
    to_buy: need,
    need,
    on_order: 0,
    reasons,
    size: DEFAULT_SIZE,
    history: reasons.map((reason) => added(reason.spools, reason.by)),
    dismissed_need: null,
    new_since_dismissal: null,
  };
}

export function added(spools: number, by: string | null = "frank"): ShoppingHistoryEntry {
  return {
    action: "added_by_hand",
    spools,
    size_g: null,
    on_order: 0,
    by,
    at: "2026-11-21T12:00:00Z",
  };
}

/** A print request short of the product: named and linked, or `null` for one the viewer may
 * not see. */
export function requestReason(
  id: number | null,
  shortG: number,
  title: string | null = id === null ? null : "Lamp shade",
): RequestReason {
  return { kind: "request", request_id: id, title, short_g: shortG };
}

/** An open suggestion by vic: of a product, unless overridden with a catalog color. */
export function suggestion(id: number, overrides: Partial<Suggestion> = {}): Suggestion {
  return {
    id,
    product: product({ id: 100 + id, display_name: `Suggested ${id}` }),
    catalog_color: null,
    spools: 1,
    by: "vic",
    at: "2026-11-21T12:00:00Z",
    ...overrides,
  };
}

/** A suggested catalog color with no product. */
export function suggestedColor(id: number, spools = 1): Suggestion {
  return suggestion(id, {
    product: null,
    catalog_color: {
      uuid: "jade",
      name: "Jade White",
      line: "PLA Basic",
      hexes: ["F5F5F0"],
      bambu_code: "10100",
    },
    spools,
  });
}
