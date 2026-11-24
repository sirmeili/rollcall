/** Editing products on the Products page: one draft per row, saved together. */

import type { ProductChanges } from "#lib/api/stock.ts";
import type { Product, ProductSummary } from "#lib/api/types.ts";
import { NAME_LENGTH } from "#lib/product-names.ts";

/** Form values, as typed. Number inputs bind to numbers, or null when cleared. */
export interface Draft {
  display_name: string;
  low_stock_threshold: number | null;
  nearly_out_pct: number | null;
  /** A staged manual catalog link from the Catalog color dialog: a catalog color's UUID,
   * null to clear the manual link, or undefined for no change. */
  catalog_color?: string | null;
  /** The catalog name a picked color staged, so a later pick can tell whether the row's
   * name is still that one or was edited since. */
  picked_name?: string;
}

export function draftOf(product: Product): Draft {
  return {
    display_name: product.display_name,
    low_stock_threshold: product.low_stock_threshold,
    nearly_out_pct: product.nearly_out_pct,
  };
}

function wholeIn(value: number | null, max: number): value is number {
  return value !== null && Number.isInteger(value) && value >= 0 && value <= max;
}

/** What is wrong with a draft, or null. Limits match the server's. */
export function draftProblem(draft: Draft): string | null {
  const name = draft.display_name.trim();
  if (!name) return "Enter a name.";
  if (name.length > NAME_LENGTH) return `Names are at most ${NAME_LENGTH} characters.`;
  if (!wholeIn(draft.low_stock_threshold, 1000)) return "Low at: a whole number, 0 to 1000.";
  if (!wholeIn(draft.nearly_out_pct, 100)) return "Nearly out: a whole number, 0 to 100.";
  return null;
}

/** The fields that differ from the saved product, or null if none do. */
export function changesFor(product: Product, draft: Draft): ProductChanges | null {
  const changes: ProductChanges = {};
  const name = draft.display_name.trim();
  if (name !== product.display_name) changes.display_name = name;
  if (draft.low_stock_threshold !== product.low_stock_threshold) {
    changes.low_stock_threshold = draft.low_stock_threshold ?? undefined;
  }
  if (draft.nearly_out_pct !== product.nearly_out_pct) {
    changes.nearly_out_pct = draft.nearly_out_pct ?? undefined;
  }
  if (draft.catalog_color !== undefined) changes.catalog_color = draft.catalog_color;
  return Object.keys(changes).length ? changes : null;
}

export function spoolCount(item: ProductSummary): number {
  const { sealed, open, empty, unknown } = item.counts;
  return sealed + open + empty + unknown;
}

export function unsavedText(count: number): string {
  return count === 1 ? "1 product changed" : `${count} products changed`;
}

/** Where a product came from: a scanned tag, or, until one of its tags is scanned, the AMS,
 * a catalog color put on the shopping list, or someone adding it by hand. */
export function sourceText(
  product: Product,
): "From tag" | "From the AMS" | "From the catalog" | "Added by hand" {
  if (!product.provisional) return "From tag";
  if (product.from_ams) return "From the AMS";
  return product.from_catalog ? "From the catalog" : "Added by hand";
}
