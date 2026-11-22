/** Add to shopping list: what can be added (every product, and the catalog colors still sold
 * that no product is linked to), searching it, and the number of spools. */

import type { Catalog } from "#lib/api/catalog.ts";
import type { AddTarget } from "#lib/api/shopping.ts";
import type { Product } from "#lib/api/types.ts";
import { rgbHex, type WholeRange } from "#lib/format.ts";

/** The server's limit: more than anyone would buy at once. */
export const MAX_SPOOLS = 999;

export interface AddOption {
  /** "p:12" for a product, "c:<uuid>" for a catalog color. */
  key: string;
  target: AddTarget;
  name: string;
  /** RRGGBB, for the swatch. */
  hexes: string[];
  /** "PLA · product", "PLA · 10100 · catalog color" */
  sub: string;
  /** The words a search looks in. */
  hay: string;
}

export function addOptions(products: Product[], catalog: Catalog | null): AddOption[] {
  const options: AddOption[] = products.map((p) => ({
    key: `p:${p.id}`,
    target: { product_id: p.id },
    name: p.display_name,
    hexes: [rgbHex(p.color_rgba)],
    sub: `${p.filament_type} · product`,
    hay: `${p.display_name} ${p.filament_type}`,
  }));
  for (const line of catalog?.lines ?? []) {
    for (const color of line.colors) {
      // A color with a linked product is offered as that product.
      const linked = color.owned_products.length > 0 || color.linked_none_in_stock.length > 0;
      if (linked || color.discontinued) continue;
      const code = color.bambu_code ? ` · ${color.bambu_code}` : "";
      options.push({
        key: `c:${color.uuid}`,
        target: { catalog_color: color.uuid },
        name: `${color.name} ${line.name}`,
        hexes: color.hexes,
        sub: `${line.material}${code} · catalog color`,
        hay: `${color.name} ${line.name} ${line.material} ${color.bambu_code ?? ""}`,
      });
    }
  }
  return options;
}

/** The options that have every word typed, products first; none until something is typed. */
export function searchAdd(options: AddOption[], query: string, most = 8): AddOption[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];
  return options
    .filter((option) => {
      const hay = option.hay.toLowerCase();
      return words.every((word) => hay.includes(word));
    })
    .slice(0, most);
}

/** The spools added, ordered or suggested at once. */
export const SPOOLS: WholeRange = { label: "Spools", min: 1, max: MAX_SPOOLS };
