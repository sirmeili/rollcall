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
  /** need - on order, never below 0. */
  to_buy: number;
  /** The spools its reasons add up to. */
  need: number;
  /** Spools ordered and not yet arrived. */
  on_order: number;
  /** Low stock first, then hand-added, oldest first. */
  reasons: ShoppingReason[];
  /** The most recent entries, newest first. */
  history: ShoppingHistoryEntry[];
}

/** A filament line's items, from their products' catalog links. */
export interface ShoppingLine {
  name: string;
  /** The line's items' to buy, added up. */
  to_buy: number;
  /** By product name. */
  items: ShoppingListItem[];
}

/** A suggested catalog color. Its fields are null once the catalog has dropped it. */
export interface SuggestedColor {
  uuid: string;
  name: string | null;
  line: string | null;
  /** RRGGBB, the main color first. */
  hexes: string[] | null;
  bambu_code: string | null;
}

/** An open suggestion: of a product, or of a catalog color no product was linked to. */
export interface Suggestion {
  id: number;
  product: Product | null;
  catalog_color: SuggestedColor | null;
  spools: number;
  /** Who suggested it; null for a token. */
  by: string | null;
  at: string;
}

export interface ShoppingList {
  /** Open suggestions, oldest first; they count toward nothing. */
  suggestions: Suggestion[];
  /** By name. */
  lines: ShoppingLine[];
  /** Products with no catalog link, by name. */
  not_in_catalog: ShoppingListItem[];
  /** The store Find in store searches, without a trailing slash. */
  store_address: string;
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

/** Add spools just ordered to a product's on order (Editor and Admin); answers the list as it
 * now stands. */
export function markOrdered(productId: number, spools: number): Promise<ShoppingList> {
  return api<ShoppingList>(`/shopping-list/items/${productId}/ordered`, {
    method: "POST",
    body: { spools },
  });
}

/** Set a product's on order to any number (Editor and Admin); answers the list as it now
 * stands. */
export function setOnOrder(productId: number, onOrder: number): Promise<ShoppingList> {
  return api<ShoppingList>(`/shopping-list/items/${productId}/on-order`, {
    method: "PUT",
    body: { on_order: onOrder },
  });
}

/** Suggest spools of a product or a catalog color (every role); answers the list as it now
 * stands. */
export function suggest(target: AddTarget, spools: number): Promise<ShoppingList> {
  return api<ShoppingList>("/shopping-list/suggestions", {
    method: "POST",
    body: { ...target, spools },
  });
}

/** Add an open suggestion, making it a hand-added reason (Editor and Admin). */
export function addSuggestion(id: number): Promise<ShoppingList> {
  return api<ShoppingList>(`/shopping-list/suggestions/${id}/add`, { method: "POST" });
}

/** Dismiss an open suggestion (Editor and Admin). */
export function dismissSuggestion(id: number): Promise<ShoppingList> {
  return api<ShoppingList>(`/shopping-list/suggestions/${id}/dismiss`, { method: "POST" });
}

/** How many suggestions are open, for the badge on the Shopping list link. */
export async function suggestionCount(): Promise<number> {
  return (await getShoppingList()).suggestions.length;
}
