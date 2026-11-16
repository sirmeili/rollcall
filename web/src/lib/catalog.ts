/** The Catalog page's search and filters, run over the whole catalog in the browser. */

import type { CatalogColor, FilamentLine } from "#lib/api/catalog.ts";
import { chosenTypes } from "#lib/inventory.ts";

export interface CatalogFilter {
  /** Matches filament line or catalog color names. */
  query: string;
  /** Materials to show; none picked shows them all. */
  types: string[];
  /** Only catalog colors with a similar in-stock color. */
  similarOnly: boolean;
  /** Discontinued catalog colors are hidden unless this is on. */
  showDiscontinued: boolean;
}

/** A filament line with the catalog colors the filter leaves, and how many it has under
 * the discontinued setting alone. */
export interface LineGroup {
  line: FilamentLine;
  colors: CatalogColor[];
  total: number;
}

export function noFilter(): CatalogFilter {
  return { query: "", types: [], similarOnly: false, showDiscontinued: false };
}

/** The materials in the catalog, in the order their first filament line comes. */
export function materials(lines: FilamentLine[]): string[] {
  return [...new Set(lines.map((line) => line.material))];
}

/** Catalog colors per material, as the filter sheet shows them. */
export function materialCounts(
  lines: FilamentLine[],
  showDiscontinued: boolean,
): { type: string; count: number }[] {
  return materials(lines).map((type) => ({
    type,
    count: countColors(applyFilter(lines, { ...noFilter(), types: [type], showDiscontinued })),
  }));
}

/** How many filters are on, for the Filter button. */
export function activeFilters(filter: CatalogFilter, available: string[]): number {
  return (
    (chosenTypes(filter.types, available).length > 0 ? 1 : 0) +
    (filter.similarOnly ? 1 : 0) +
    (filter.showDiscontinued ? 1 : 0)
  );
}

/** Whether the search or any filter is narrowing the list. */
export function isFiltered(filter: CatalogFilter): boolean {
  return (
    filter.query.trim() !== "" ||
    filter.types.length > 0 ||
    filter.similarOnly ||
    filter.showDiscontinued
  );
}

/** The filament lines with the catalog colors the filter leaves; a line with none left is
 * dropped. A search that matches a line's name keeps the whole line. */
export function applyFilter(lines: FilamentLine[], filter: CatalogFilter): LineGroup[] {
  const query = filter.query.trim().toLowerCase();
  const groups: LineGroup[] = [];
  for (const line of lines) {
    if (filter.types.length && !filter.types.includes(line.material)) continue;
    const pool = line.colors.filter((color) => filter.showDiscontinued || !color.discontinued);
    const lineMatches = query !== "" && line.name.toLowerCase().includes(query);
    const colors = pool.filter(
      (color) =>
        (!filter.similarOnly || color.similar.length > 0) &&
        (!query || lineMatches || color.name.toLowerCase().includes(query)),
    );
    if (colors.length) groups.push({ line, colors, total: pool.length });
  }
  return groups;
}

export function countColors(groups: LineGroup[]): number {
  return groups.reduce((sum, group) => sum + group.colors.length, 0);
}

function lines(n: number): string {
  return n === 1 ? "filament line" : "filament lines";
}

/** "304 catalog colors in 50 filament lines", or "12 of 304 catalog colors in 3 filament
 * lines" while a search or filter is on. */
export function summaryText(all: FilamentLine[], filter: CatalogFilter): string {
  const groups = applyFilter(all, filter);
  const shown = countColors(groups);
  const total = countColors(
    applyFilter(all, { ...noFilter(), showDiscontinued: filter.showDiscontinued }),
  );
  const count = isFiltered(filter) ? `${shown} of ${total}` : `${total}`;
  return `${count} catalog colors in ${groups.length} ${lines(groups.length)}`;
}

/** The heading's count: "30 colors", or "4 of 30 colors" when some are filtered out. */
export function lineCountText(group: LineGroup): string {
  const n = group.colors.length;
  return n === group.total
    ? `${n} ${n === 1 ? "color" : "colors"}`
    : `${n} of ${group.total} colors`;
}

/** "2 sealed · 1 open" */
export function stockText(sealed: number, open: number): string {
  return [sealed ? `${sealed} sealed` : "", open ? `${open} open` : ""].filter(Boolean).join(" · ");
}

/** "ΔE 3.1" */
export function deltaText(deltaE: number): string {
  return `ΔE ${deltaE.toFixed(1)}`;
}

/** "ΔE 10", "ΔE 2.5": the cutoff as it was set. */
export function cutoffText(cutoff: number): string {
  return `ΔE ${cutoff}`;
}

/** "#9CDBD9 / #FFFFFF" */
export function hexText(hexes: string[]): string {
  return hexes.map((hex) => `#${hex}`).join(" / ");
}
