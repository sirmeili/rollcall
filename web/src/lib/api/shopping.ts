import { api } from "#lib/api/client.ts";
import type { Product } from "#lib/api/types.ts";

/** The product is low: buying `spools` takes its Sealed count above its threshold. */
export interface LowStockReason {
  kind: "low_stock";
  spools: number;
  sealed: number;
  threshold: number;
}

/** Spools an Editor or Admin added by hand. */
export interface HandReason {
  kind: "hand";
  id: number;
  spools: number;
  /** Who added them; null for a token. */
  by: string | null;
  at: string;
}

export type ShoppingReason = LowStockReason | HandReason;

export type ShoppingAction =
  | "added_by_hand"
  | "removed_by_hand"
  | "suggested"
  | "suggestion_added"
  | "suggestion_dismissed"
  | "ordered"
  | "on_order_changed"
  | "dismissed"
  | "brought_back"
  | "size_changed"
  | "same_product";

/** One entry in an item's shopping list history. */
export interface ShoppingHistoryEntry {
  action: ShoppingAction;
  /** The spools or the size in grams the action concerned, if any. */
  spools: number | null;
  size_g: number | null;
  /** The item's on order once it was done. */
  on_order: number;
  /** Who did it; null for a token. */
  by: string | null;
  at: string;
}

/** One product on the shopping list, with the reasons it is there. */
export interface ShoppingListItem {
  product: Product;
  to_buy: number;
  /** Low stock first, then hand-added, oldest first. */
  reasons: ShoppingReason[];
  /** The most recent entries, newest first. */
  history: ShoppingHistoryEntry[];
  /** The need it was dismissed at; null when it is not dismissed. */
  dismissed_need: number | null;
  /** How many spools more it needs than when it was dismissed, once that is more. */
  new_since_dismissal: number | null;
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
  /** Dismissed items still hidden: no more is needed than when dismissed. By name. */
  dismissed: ShoppingListItem[];
}

/** What to add spools to: a product, or a catalog color (its product, made "From the catalog"
 * if it has none). */
export type AddTarget = { product_id: number } | { catalog_color: string };

/** The shopping list (every role). */
export function getShoppingList(): Promise<ShoppingList> {
  return api<ShoppingList>("/shopping-list");
}

/** Add spools by hand (Editor and Admin); answers the list as it now stands. */
export function addByHand(target: AddTarget, spools: number): Promise<ShoppingList> {
  return api<ShoppingList>("/shopping-list/hand-reasons", {
    method: "POST",
    body: { ...target, spools },
  });
}

/** Remove a hand-added reason (Editor and Admin); answers the list as it now stands. */
export function removeHandReason(id: number): Promise<ShoppingList> {
  return api<ShoppingList>(`/shopping-list/hand-reasons/${id}`, { method: "DELETE" });
}

/** Dismiss a product's item (Editor and Admin): hide it until more of it is needed than now,
 * and remove its hand-added reasons. Answers the list as it now stands. */
export function dismissItem(productId: number): Promise<ShoppingList> {
  return api<ShoppingList>(`/shopping-list/items/${productId}/dismiss`, { method: "POST" });
}

/** Bring back a dismissed item (Editor and Admin); answers the list as it now stands. */
export function bringBack(productId: number): Promise<ShoppingList> {
  return api<ShoppingList>(`/shopping-list/items/${productId}/bring-back`, { method: "POST" });
}
