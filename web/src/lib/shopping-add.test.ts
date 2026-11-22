import { describe, expect, it } from "vitest";
import type { Catalog, CatalogColor } from "#lib/api/catalog.ts";
import { addOptions, searchAdd, spoolsProblem } from "#lib/shopping-add.ts";
import { product } from "../test/fixtures.ts";

function color(uuid: string, name: string, overrides: Partial<CatalogColor> = {}): CatalogColor {
  return {
    uuid,
    name,
    hexes: ["F5F5F0"],
    discontinued: false,
    multi_color: false,
    gradient: false,
    bambu_code: null,
    similar: [],
    owned: false,
    owned_products: [],
    linked_none_in_stock: [],
    ...overrides,
  };
}

const CATALOG = {
  lines: [
    {
      uuid: "pla-basic",
      name: "PLA Basic",
      material: "PLA",
      colors: [
        color("jade", "Jade White", { bambu_code: "10100" }),
        color("owned", "Black", {
          owned: true,
          owned_products: [
            {
              product_id: 1,
              name: "Black",
              hex: "000000",
              material: "PLA",
              how: "tag",
              sealed: 1,
              open: 0,
            },
          ],
        }),
        color("linked", "Red", { linked_none_in_stock: [{ product_id: 2, name: "Red" }] }),
        color("old", "Old Green", { discontinued: true }),
      ],
    },
  ],
} as unknown as Catalog;

describe("addOptions", () => {
  it("offers every product, then catalog colors no product is linked to, not discontinued", () => {
    const options = addOptions(
      [product({ id: 3, display_name: "Teal PETG", filament_type: "PETG" })],
      CATALOG,
    );

    expect(options.map((o) => [o.key, o.name, o.sub, o.target])).toEqual([
      ["p:3", "Teal PETG", "PETG · product", { product_id: 3 }],
      ["c:jade", "Jade White PLA Basic", "PLA · 10100 · catalog color", { catalog_color: "jade" }],
    ]);
    expect(options[0].hexes).toEqual(["000000"]);
  });

  it("offers only products when the catalog could not be read", () => {
    expect(addOptions([product()], null).map((o) => o.key)).toEqual(["p:1"]);
  });
});

describe("searchAdd", () => {
  const options = addOptions([product({ id: 3, display_name: "Black PLA Basic" })], CATALOG);

  it("finds nothing until something is typed", () => {
    expect(searchAdd(options, "  ")).toEqual([]);
  });

  it("matches every word, in names, materials and Bambu codes", () => {
    expect(searchAdd(options, "pla basic").map((o) => o.key)).toEqual(["p:3", "c:jade"]);
    expect(searchAdd(options, "10100").map((o) => o.key)).toEqual(["c:jade"]);
    expect(searchAdd(options, "JADE white").map((o) => o.key)).toEqual(["c:jade"]);
  });

  it("shows at most a few", () => {
    expect(searchAdd(options, "pla", 1).map((o) => o.key)).toEqual(["p:3"]);
  });
});

describe("spoolsProblem", () => {
  it("wants a whole number of spools, 1 to 999", () => {
    expect(spoolsProblem(1)).toBeNull();
    expect(spoolsProblem(999)).toBeNull();
    expect(spoolsProblem(null)).toBe("Spools: a whole number, 1 to 999.");
    expect(spoolsProblem(0)).toBe("Spools: a whole number, 1 to 999.");
    expect(spoolsProblem(1.5)).toBe("Spools: a whole number, 1 to 999.");
    expect(spoolsProblem(1000)).toBe("Spools: a whole number, 1 to 999.");
  });
});
