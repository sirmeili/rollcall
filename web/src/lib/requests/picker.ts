/** The filament picker on the request form: in-stock products, then catalog colors no one
 * has in stock (not discontinued ones). */

import type { Catalog } from "#lib/api/catalog.ts";
import type { Choice, ChoiceIn } from "#lib/api/requests.ts";
import type { ProductSummary } from "#lib/api/types.ts";
import { stockText, storeSearchUrl, storeUrl } from "#lib/catalog.ts";
import { similarText } from "#lib/requests/labels.ts";
import { aboutGrams } from "#lib/spools.ts";

interface OptionBase {
  /** "p:12" for a product, "c:<uuid>" for a catalog color: the list and identity key. */
  key: string;
  name: string;
  hexes: string[];
  /** "PLA · 2 sealed · 1 open · about 1120 g", "PLA · 10101 · not in stock" */
  sub: string;
  /** A catalog color's similar in-stock products; null for a multi-color one. */
  similar: string[] | null;
  /** The words a search looks in. */
  hay: string;
  /** A catalog color the catalog has dropped since it was chosen. */
  gone?: boolean;
}

export type FilamentOption =
  | (OptionBase & { kind: "product"; productId: number })
  | (OptionBase & {
      kind: "catalog_color";
      uuid: string;
      /** Find in store's search for it. */
      storeHref: string;
    });

/** A choice on the form, in order. */
export type Chosen = FilamentOption & { note: string };

export interface PickerOptions {
  products: FilamentOption[];
  colors: FilamentOption[];
}

/** A product's grams not held: "about 1120 g", or "grams unknown" when an open spool's are. */
function gramsText(item: Pick<ProductSummary, "available_g" | "available_unknown">): string {
  return item.available_unknown ? "grams unknown" : aboutGrams(item.available_g);
}

export function pickerOptions(inventory: ProductSummary[], catalog: Catalog | null): PickerOptions {
  const products = inventory
    .filter((item) => item.counts.sealed + item.counts.open > 0)
    .map(({ product, counts, ...grams }) => ({
      key: `p:${product.id}`,
      kind: "product" as const,
      productId: product.id,
      name: product.display_name,
      hexes: [product.color_rgba.slice(0, 6).toUpperCase()],
      sub: `${product.filament_type} · ${stockText(counts.sealed, counts.open)} · ${gramsText(grams)}`,
      similar: [],
      hay: `${product.display_name} ${product.filament_type}`,
    }));
  const colors: FilamentOption[] = [];
  const storeAddress = catalog?.store_address ?? "";
  for (const line of catalog?.lines ?? []) {
    for (const color of line.colors) {
      if (color.discontinued || color.owned) continue;
      const code = color.bambu_code ? ` · ${color.bambu_code}` : "";
      colors.push({
        key: `c:${color.uuid}`,
        kind: "catalog_color",
        uuid: color.uuid,
        storeHref: storeUrl(storeAddress, line.name, color),
        name: `${color.name} ${line.name}`,
        hexes: color.hexes,
        sub: `${line.material}${code} · not in stock`,
        similar: color.multi_color ? null : color.similar.map((match) => match.name),
        hay: `${color.name} ${line.name} ${line.material} ${color.bambu_code ?? ""}`,
      });
    }
  }
  return { products, colors };
}

/** A choice already on a request, as the form shows it. storeAddress: the store Find in
 * store searches. */
export function chosenFrom(choice: Choice, storeAddress: string): Chosen {
  if (choice.kind === "product") {
    return {
      key: `p:${choice.product_id}`,
      kind: "product",
      productId: choice.product_id as number,
      name: choice.name,
      hexes: choice.hexes,
      sub: [choice.material, stockText(choice.sealed ?? 0, choice.open ?? 0) || "none left"]
        .filter(Boolean)
        .join(" · "),
      similar: [],
      hay: choice.name,
      note: choice.note,
    };
  }
  const code = choice.bambu_code ? ` · ${choice.bambu_code}` : "";
  return {
    key: `c:${choice.catalog_color}`,
    kind: "catalog_color",
    uuid: choice.catalog_color as string,
    storeHref: storeSearchUrl(
      storeAddress,
      choice.line ?? "",
      choice.color_name ?? choice.name,
      choice.bambu_code,
    ),
    name: choice.name,
    hexes: choice.hexes,
    sub: choice.in_catalog
      ? `${choice.material ?? ""}${code} · not in stock`
      : "No longer in the catalog",
    similar: choice.multi_color ? null : choice.similar.map((match) => match.name),
    hay: choice.name,
    gone: !choice.in_catalog,
    note: choice.note,
  };
}

/** The line under a choice: its stock, or for a catalog color, what is similar in stock. */
export function chosenSub(option: FilamentOption, most?: number): string {
  if (option.kind === "product" || option.gone) return option.sub;
  return `${option.sub} · ${similarText(option.similar, most)}`;
}

export function choiceIn(chosen: Chosen): ChoiceIn {
  const note = chosen.note.trim();
  return chosen.kind === "product"
    ? { product_id: chosen.productId, note }
    : { catalog_color: chosen.uuid, note };
}

const FIRST_PRODUCTS = 5;
const MOST_COLORS = 5;

export interface SearchResult {
  products: FilamentOption[];
  colors: FilamentOption[];
  /** Says what is shown, for the status line under the search. */
  summary: string;
}

/** With no words, the first few products; otherwise every product and up to five catalog
 * colors that have every word. */
export function searchOptions(options: PickerOptions, query: string): SearchResult {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) {
    const products = options.products.slice(0, FIRST_PRODUCTS);
    return {
      products,
      colors: [],
      summary: `Showing ${products.length} of your ${options.products.length} products. Type to search all of them and the catalog.`,
    };
  }
  const matches = (option: FilamentOption) => {
    const hay = option.hay.toLowerCase();
    return words.every((word) => hay.includes(word));
  };
  const products = options.products.filter(matches);
  const allColors = options.colors.filter(matches);
  const colors = allColors.slice(0, MOST_COLORS);
  if (products.length + colors.length === 0) {
    return { products, colors, summary: `Nothing matches "${query.trim()}".` };
  }
  const colorWord = allColors.length === 1 ? "color" : "colors";
  const more = allColors.length > MOST_COLORS ? ` (showing ${MOST_COLORS})` : "";
  return {
    products,
    colors,
    summary: `${products.length} of your products, ${allColors.length} catalog ${colorWord}${more}`,
  };
}
