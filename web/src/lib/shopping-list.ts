import type {
  ShoppingHistoryEntry,
  ShoppingList,
  ShoppingListItem,
  ShoppingReason,
  ShoppingSize,
  Suggestion,
} from "#lib/api/shopping.ts";
import type { Product } from "#lib/api/types.ts";
import { storeSearchUrl } from "#lib/catalog.ts";
import { dateTime } from "#lib/format.ts";

/** The largest size an item can be given, as the largest net weight a spool can have. */
const MAX_SIZE_G = 10_000;

/** "1 spool", "3 spools" */
export function spoolsText(spools: number): string {
  return `${spools} ${spools === 1 ? "spool" : "spools"}`;
}

/** Why an item is on the list: "Low stock: 1 sealed, threshold 2 · 2 spools", "Lamp shade ·
 * 300 g short", "A print request · 300 g short", "Added by hand by frank · 1 spool". */
export function reasonText(reason: ShoppingReason): string {
  if (reason.kind === "request") {
    return `${reason.title ?? "A print request"} · ${reason.short_g} g short`;
  }
  if (reason.kind === "hand") {
    const by = reason.by ? ` by ${reason.by}` : "";
    return `Added by hand${by} · ${spoolsText(reason.spools)}`;
  }
  return `Low stock: ${reason.sealed} sealed, threshold ${reason.threshold} · ${spoolsText(reason.spools)}`;
}

/** What a history entry records: "Added 2 spools by hand", "Ordered 2 spools". */
export function historyText(entry: ShoppingHistoryEntry): string {
  const spools = spoolsText(entry.spools ?? 0);
  if (entry.action === "added_by_hand") return `Added ${spools} by hand`;
  if (entry.action === "removed_by_hand") return `Removed ${spools} added by hand`;
  if (entry.action === "ordered") return `Ordered ${spools}`;
  if (entry.action === "on_order_changed") return "Changed on order";
  if (entry.action === "size_changed") return `Size set to ${entry.size_g ?? 0} g`;
  if (entry.action === "suggested") return `Suggested ${spools}`;
  if (entry.action === "suggestion_added") return `Added a suggestion of ${spools}`;
  if (entry.action === "suggestion_dismissed") return `Dismissed a suggestion of ${spools}`;
  if (entry.action === "same_product") return "Made one product with a possible duplicate";
  const words = entry.action.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const SIZE_FROM: Record<ShoppingSize["source"], string> = {
  chosen: "chosen",
  last_spool: "from the last spool received",
  catalog: "from the catalog",
  default: "the default",
};

/** The size an item turns its requests' grams into spools with: "1000 g spools (from the
 * last spool received)". */
export function sizeText(size: ShoppingSize): string {
  return `${size.grams} g spools (${SIZE_FROM[size.source]})`;
}

/** Why a size can't be chosen, or null. */
export function sizeProblem(grams: number | null): string | null {
  const whole = grams !== null && Number.isInteger(grams) && grams >= 1;
  return whole && grams <= MAX_SIZE_G ? null : `Size: a whole number of grams, 1 to 10,000.`;
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

/** What was suggested: the product's name, or the catalog color and its line. */
export function suggestionName(suggestion: Suggestion): string {
  if (suggestion.product) return suggestion.product.display_name;
  const color = suggestion.catalog_color;
  return color?.name ? `${color.name} ${color.line}` : "A color no longer in the catalog";
}

/** The suggestion's swatch colors, RRGGBB. */
export function suggestionHexes(suggestion: Suggestion): string[] {
  if (suggestion.product) return [suggestion.product.color_rgba.slice(0, 6).toUpperCase()];
  return suggestion.catalog_color?.hexes ?? [];
}

/** "2 spools · catalog color · suggested by vic · Nov 21, 12:00 PM" */
export function suggestionText(suggestion: Suggestion, now: Date = new Date()): string {
  const kind = suggestion.product ? suggestion.product.filament_type : "catalog color";
  const by = suggestion.by ? `suggested by ${suggestion.by}` : "suggested";
  return [spoolsText(suggestion.spools), kind, by, dateTime(suggestion.at, now)].join(" · ");
}
