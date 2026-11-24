/** Catalog links on the Products page: the Catalog color column's words, and the Catalog
 * color dialog's search and staged change. */

import type { Catalog, CatalogColor } from "#lib/api/catalog.ts";
import type { CatalogLink, Product } from "#lib/api/types.ts";
import { howText } from "#lib/catalog.ts";
import { longDate } from "#lib/format.ts";
import { catalogName, isDefaultName } from "#lib/product-names.ts";
import type { Draft } from "#lib/products.ts";

/** A catalog color with its filament line, as the dialog lists it. */
export interface CatalogEntry {
  color: CatalogColor;
  line: string;
  material: string;
}

/** The dialog's search shows at most this many results. */
export const MAX_RESULTS = 6;

/** "PLA Basic · Black" */
export function linkName(line: string | null, name: string | null): string {
  return `${line ?? ""} · ${name ?? ""}`;
}

/** "Linked by hand by frank, 17 Nov 2026" */
export function handText(link: CatalogLink): string {
  const by = link.linked_by ? ` by ${link.linked_by}` : "";
  return `Linked by hand${by}, ${longDate(link.linked_at)}`;
}

/** What a manual link to a dropped color was: "Was PLA Glow · Green, linked by hand by
 * frank, 2 Mar 2026. Pick a new color or clear it." */
export function droppedText(link: CatalogLink): string {
  const was = linkName(link.was_line, link.was_name);
  const how = handText(link).replace("Linked", "linked");
  return `Was ${was}, ${how}. Pick a new color or clear it.`;
}

/** The Catalog color cell's accessible name. */
export function cellLabel(productName: string, link: CatalogLink | null): string {
  let what: string;
  if (!link) what = "not linked";
  else if (!link.in_catalog) what = "no longer in the catalog";
  else what = `${linkName(link.line, link.name)}, ${howText(link.how).toLowerCase()}`;
  return `Catalog color for ${productName}: ${what}. Change`;
}

/** What Clear will do. */
export function clearHint(tagLinkExists: boolean): string {
  return tagLinkExists
    ? "Clearing goes back to the color from its tag."
    : "This product has no tag, so clearing leaves it not linked.";
}

/** Every catalog color with its line, in catalog order. */
export function catalogEntries(catalog: Catalog): CatalogEntry[] {
  return catalog.lines.flatMap((line) =>
    line.colors.map((color) => ({ color, line: line.name, material: line.material })),
  );
}

/** A result's accessible name: "Green, PLA Basic, no Bambu code". */
export function entryLabel(entry: CatalogEntry): string {
  const code = entry.color.bambu_code;
  return `${entry.color.name}, ${entry.line}, ${code ? `Bambu code ${code}` : "no Bambu code"}`;
}

export interface SearchResult {
  /** At most MAX_RESULTS. */
  shown: CatalogEntry[];
  /** What the search found, for the count line. */
  text: string;
}

/** Catalog colors whose name, line or Bambu code holds every word typed. With nothing
 * typed, the colors of the product's material. */
export function searchEntries(
  entries: CatalogEntry[],
  query: string,
  material: string,
): SearchResult {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) {
    const hits = entries.filter((e) => e.material.toLowerCase() === material.toLowerCase());
    const more =
      hits.length > MAX_RESULTS
        ? `, first ${MAX_RESULTS} of ${hits.length}. Type to search all ${entries.length}.`
        : "";
    return { shown: hits.slice(0, MAX_RESULTS), text: `${material} colors${more}` };
  }
  const hits = entries.filter((e) => {
    const hay = `${e.color.name} ${e.line} ${e.color.bambu_code ?? ""}`.toLowerCase();
    return words.every((word) => hay.includes(word));
  });
  if (!hits.length) return { shown: [], text: `No catalog colors match "${query.trim()}".` };
  const count = `${hits.length} ${hits.length === 1 ? "match" : "matches"}`;
  const more = hits.length > MAX_RESULTS ? `, showing the first ${MAX_RESULTS}` : "";
  return { shown: hits.slice(0, MAX_RESULTS), text: `${count}${more}` };
}

/** A staged change to a product's manual link: a catalog color's UUID sets one, null
 * clears it, undefined leaves it. */
export type LinkPick = string | null | undefined;

/** The name staged with a picked color: its catalog name, when the product has no effective
 * link and the name in its row (staged or saved) is still its default name. Otherwise
 * undefined, and the row's name is left as it is. */
function nameForPick(
  product: Product,
  rowName: string,
  entry: CatalogEntry | undefined,
): string | undefined {
  if (!entry || product.catalog_link?.in_catalog) return undefined;
  if (!isDefaultName(rowName.trim(), product.color_rgba)) return undefined;
  return catalogName(entry.color.name, entry.line);
}

/** Stage a pick from the Catalog color dialog on a row's draft, with the name it brings
 * (see nameForPick). A name a pick staged, and not edited since, follows later picks:
 * another color replaces it with that color's catalog name, and clearing the link puts the
 * saved name back. A name typed or edited in the row is never touched. */
export function stagePick(
  product: Product,
  draft: Draft,
  pick: LinkPick,
  entry: CatalogEntry | undefined,
): void {
  draft.catalog_color = pick;
  if (draft.picked_name !== undefined && draft.display_name === draft.picked_name) {
    draft.display_name = product.display_name;
  }
  draft.picked_name = nameForPick(product, draft.display_name, entry);
  if (draft.picked_name !== undefined) draft.display_name = draft.picked_name;
}

/** The change a pick makes to the saved link: undefined when it changes nothing (the same
 * manual link again, or clearing when there is no manual link). */
export function changeFor(link: CatalogLink | null, pick: LinkPick): LinkPick {
  const manual = link?.how === "hand";
  if (pick === undefined) return undefined;
  if (pick === null) return manual ? null : undefined;
  return manual && link?.uuid === pick ? undefined : pick;
}
