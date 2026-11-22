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

/** A print request holding filament that is short of the product. */
export interface RequestReason {
  kind: "request";
  /** The request, for people allowed to see it; otherwise null. */
  request_id: number | null;
  /** Its title, for people allowed to see it; otherwise null ("a print request"). */
  title: string | null;
  short_g: number;
}

export type ShoppingReason = LowStockReason | RequestReason | HandReason;

/** Where an item's size came from. */
export type SizeFrom = "chosen" | "last_spool" | "catalog" | "default";

/** The size an item rounds its requests' grams, added up, to spools with. */
export interface ShoppingSize {
  grams: number;
  source: SizeFrom;
}

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
  /** Low stock first, then the requests short of it, then hand-added, oldest first. */
  reasons: ShoppingReason[];
  size: ShoppingSize;
  /** The most recent entries, newest first. */
  shopping_history: ShoppingHistoryEntry[];
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

/** Choose the size an item rounds its requests' grams to spools with (Editor and Admin);
 * answers the list as it now stands. */
export function setSize(productId: number, sizeG: number): Promise<ShoppingList> {
  return api<ShoppingList>(`/shopping-list/items/${productId}/size`, {
    method: "PUT",
    body: { size_g: sizeG },
  });
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
