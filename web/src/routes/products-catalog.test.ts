import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Catalog, CatalogColor } from "#lib/api/catalog.ts";
import type { CatalogLink } from "#lib/api/types.ts";
import { setTimeZone } from "#lib/format.ts";
import type { Role } from "#lib/roles.ts";
import { me, product, summary } from "../test/fixtures.ts";

const stock = vi.hoisted(() => ({ getInventory: vi.fn(), updateProduct: vi.fn() }));
vi.mock("#lib/api/stock.ts", () => stock);
const catalogApi = vi.hoisted(() => ({ getCatalog: vi.fn() }));
vi.mock("#lib/api/catalog.ts", () => catalogApi);

const { session } = await import("#lib/auth/session.svelte.ts");
const ProductsPage = (await import("./products/+page.svelte")).default;

function link(fields: Partial<CatalogLink> = {}): CatalogLink {
  return {
    uuid: "var-black",
    name: "Black",
    line: "PLA Basic",
    hexes: ["000000"],
    bambu_code: "10101",
    how: "tag",
    in_catalog: true,
    linked_by: null,
    linked_at: null,
    was_line: null,
    was_name: null,
    tag_link_exists: true,
    ...fields,
  };
}

function color(uuid: string, name: string, hex: string, code: string | null): CatalogColor {
  return {
    uuid,
    name,
    hexes: [hex],
    discontinued: false,
    multi_color: false,
    gradient: false,
    bambu_code: code,
    similar: [],
    owned: false,
    owned_products: [],
    linked_none_in_stock: [],
  };
}

const CATALOG: Catalog = {
  lines: [
    {
      uuid: "pla-basic",
      name: "PLA Basic",
      material: "PLA",
      colors: [
        color("var-black", "Black", "000000", "10101"),
        color("var-jade", "Jade White", "FFFFFF", "10100"),
        color("var-green", "Green", "00AE42", null),
      ],
    },
    {
      uuid: "petg-hf",
      name: "PETG HF",
      material: "PETG",
      colors: [color("var-petg-black", "Black", "000000", "33102")],
    },
  ],
  synced: true,
  dataset_version: "2026.11.15",
  last_success_at: "2026-11-15T04:00:00Z",
  cutoff: 10,
  out_of_date: false,
  store_address: "https://us.store.bambulab.com",
};

const BY_TAG = summary({ product: product({ id: 1, catalog_link: link() }) });
const BY_HAND = summary({
  product: product({
    id: 2,
    display_name: "White PLA",
    color_rgba: "FFFFFFFF",
    provisional: true,
    material_id: null,
    variant_id: null,
    catalog_link: link({
      uuid: "var-jade",
      name: "Jade White",
      hexes: ["FFFFFF"],
      bambu_code: "10100",
      how: "hand",
      linked_by: "frank",
      linked_at: "2026-11-17T10:00:00Z",
      tag_link_exists: false,
    }),
  }),
});
const NOT_LINKED = summary({
  product: product({
    id: 3,
    display_name: "Teal PETG",
    filament_type: "PETG",
    color_rgba: "008080FF",
    provisional: true,
    catalog_link: null,
  }),
});
const DROPPED = summary({
  product: product({
    id: 4,
    display_name: "Glow green",
    color_rgba: "7FFF00FF",
    catalog_link: link({
      uuid: null,
      name: null,
      line: null,
      hexes: null,
      bambu_code: null,
      how: "hand",
      in_catalog: false,
      linked_by: "frank",
      linked_at: "2026-03-02T10:00:00Z",
      was_line: "PLA Glow",
      was_name: "Green",
    }),
  }),
});

function signedInAs(role: Role): void {
  session.user = me(role);
  session.loaded = true;
}

/** The Catalog color cell of a product's row. */
function cell(name: string) {
  const row = screen
    .getAllByRole("row")
    .find((r) => r.textContent?.includes(name) || within(r).queryByDisplayValue(name));
  const index = screen
    .getAllByRole("columnheader")
    .findIndex((h) => h.textContent === "Catalog color");
  return within(within(row!).getAllByRole("cell")[index]);
}

async function openDialog(name: string) {
  await userEvent.click(
    await screen.findByRole("button", { name: new RegExp(`^Catalog color for ${name}:`) }),
  );
  return within(await screen.findByRole("dialog", { name: "Catalog color" }));
}

beforeEach(() => {
  vi.useFakeTimers({ now: new Date("2026-11-17T15:00:00Z"), shouldAdvanceTime: true });
  setTimeZone("UTC");
  signedInAs("editor");
  stock.getInventory.mockResolvedValue([BY_TAG, BY_HAND, NOT_LINKED, DROPPED]);
  catalogApi.getCatalog.mockResolvedValue(CATALOG);
});

afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
  setTimeZone(undefined);
});

describe("Products page, Catalog color column", () => {
  it("shows each product's catalog color and how it was linked, after its color", async () => {
    render(ProductsPage);

    await screen.findByDisplayValue("White PLA");
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers.indexOf("Catalog color")).toBe(headers.indexOf("Color") + 1);
    expect(cell("Black PLA Basic").getByText("PLA Basic · Black")).toBeInTheDocument();
    expect(cell("Black PLA Basic").getByText("From its tag")).toBeInTheDocument();
    expect(cell("White PLA").getByText("PLA Basic · Jade White")).toBeInTheDocument();
    expect(cell("White PLA").getByText("Linked by hand")).toBeInTheDocument();
    expect(cell("Teal PETG").getByText("Not linked")).toBeInTheDocument();
    expect(cell("Glow green").getByText("No longer in the catalog")).toBeInTheDocument();
  });

  it('shows "From the catalog" for a product made from a catalog color', async () => {
    const fromCatalog = summary({
      product: product({ ...BY_HAND.product, id: 5, display_name: "Jade White PLA Basic" }),
    });
    fromCatalog.product.from_catalog = true;
    stock.getInventory.mockResolvedValue([BY_HAND, fromCatalog]);
    render(ProductsPage);

    const row = (await screen.findByDisplayValue("Jade White PLA Basic")).closest("tr")!;
    expect(within(row).getByText("From the catalog")).toBeInTheDocument();
    const hand = screen.getByDisplayValue("White PLA").closest("tr")!;
    expect(within(hand).getByText("Added by hand")).toBeInTheDocument();
  });

  it("shows Viewers the column without a way to change it", async () => {
    signedInAs("viewer");
    render(ProductsPage);

    expect(await screen.findByText("PLA Basic · Jade White")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Catalog color for/ })).toBeNull();
  });

  it("names each cell's link for screen readers", async () => {
    render(ProductsPage);

    expect(
      await screen.findByRole("button", {
        name: "Catalog color for White PLA: PLA Basic · Jade White, linked by hand. Change",
      }),
    ).toHaveAttribute("aria-haspopup", "dialog");
    expect(
      screen.getByRole("button", { name: "Catalog color for Teal PETG: not linked. Change" }),
    ).toBeInTheDocument();
  });
});

describe("Products page, Catalog color dialog", () => {
  it("shows a manual link, who made it and when, with Clear and Find in store", async () => {
    render(ProductsPage);

    const dialog = await openDialog("White PLA");

    const current = within(dialog.getByRole("group", { name: "Current link" }));
    expect(current.getByText("PLA Basic · Jade White")).toBeInTheDocument();
    expect(current.getByText("10100")).toBeInTheDocument();
    expect(current.getByText("Linked by hand by frank, 17 Nov 2026")).toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "Clear" })).toBeEnabled();
    expect(
      dialog.getByText("This product has no tag, so clearing leaves it not linked."),
    ).toBeInTheDocument();
    const store = dialog.getByRole("link", { name: "Find in store (opens in a new tab)" });
    expect(store).toHaveAttribute("href", "https://us.store.bambulab.com/search?q=10100");
    expect(store).toHaveAttribute("target", "_blank");
  });

  it("offers no Clear for a link from the tag", async () => {
    render(ProductsPage);

    const dialog = await openDialog("Black PLA Basic");

    expect(dialog.getByText("From its tag")).toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "Clear" })).toBeDisabled();
    expect(dialog.getByText("Clearing goes back to the color from its tag.")).toBeInTheDocument();
  });

  it("explains a link to a color the catalog has dropped", async () => {
    render(ProductsPage);

    const dialog = await openDialog("Glow green");

    expect(dialog.getByText("No longer in the catalog")).toBeInTheDocument();
    expect(
      dialog.getByText(
        "Was PLA Glow · Green, linked by hand by frank, 2 Mar 2026. Pick a new color or clear it.",
      ),
    ).toBeInTheDocument();
    expect(dialog.queryByRole("link", { name: /Find in store/ })).toBeNull();
  });

  it("lists the product's material first and searches name, line and Bambu code", async () => {
    render(ProductsPage);

    const dialog = await openDialog("Teal PETG");

    expect(await dialog.findByText("PETG colors")).toBeInTheDocument();
    expect(dialog.getAllByRole("button", { name: /Bambu code|no Bambu code/ })).toHaveLength(1);
    const search = dialog.getByRole("searchbox", { name: "Link to a catalog color" });
    await userEvent.type(search, "green");
    expect(dialog.getByText("1 match")).toBeInTheDocument();
    expect(
      dialog.getByRole("button", { name: "Green, PLA Basic, no Bambu code" }),
    ).toBeInTheDocument();
    await userEvent.clear(search);
    await userEvent.type(search, "33102");
    expect(
      dialog.getByRole("button", { name: "Black, PETG HF, Bambu code 33102" }),
    ).toBeInTheDocument();
    await userEvent.clear(search);
    await userEvent.type(search, "pla basic");
    expect(dialog.getByText("3 matches")).toBeInTheDocument();
    await userEvent.clear(search);
    await userEvent.type(search, "mauve");
    expect(dialog.getByText('No catalog colors match "mauve".')).toBeInTheDocument();
  });

  it("stages a picked color, saved with the page's other edits in one update", async () => {
    stock.updateProduct.mockResolvedValue(product());
    render(ProductsPage);

    const dialog = await openDialog("Teal PETG");
    await userEvent.click(await dialog.findByRole("button", { name: /^Black, PETG HF/ }));
    expect(dialog.getByText("Linked by hand by frank when you save")).toBeInTheDocument();
    expect(dialog.getByText("Not saved yet")).toBeInTheDocument();
    await userEvent.click(dialog.getByRole("button", { name: "Save" }));

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(cell("Teal PETG").getByText("PETG HF · Black")).toBeInTheDocument();
    expect(cell("Teal PETG").getByText("Not saved yet")).toBeInTheDocument();
    expect(screen.getByText("1 product changed")).toBeInTheDocument();
    expect(stock.updateProduct).not.toHaveBeenCalled();

    const name = screen.getByDisplayValue("Teal PETG");
    await userEvent.type(name, " HF");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(stock.updateProduct).toHaveBeenCalledExactlyOnceWith(3, {
      display_name: "Teal PETG HF",
      catalog_color: "var-petg-black",
    });
  });

  it("clears a manual link back to none", async () => {
    stock.updateProduct.mockResolvedValue(product());
    render(ProductsPage);

    const dialog = await openDialog("White PLA");
    await userEvent.click(dialog.getByRole("button", { name: "Clear" }));
    expect(dialog.getByText("Not linked")).toBeInTheDocument();
    await userEvent.click(dialog.getByRole("button", { name: "Save" }));
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(stock.updateProduct).toHaveBeenCalledExactlyOnceWith(2, { catalog_color: null });
  });

  it("drops what was picked on Cancel or Escape", async () => {
    render(ProductsPage);

    let dialog = await openDialog("Teal PETG");
    await userEvent.click(await dialog.findByRole("button", { name: /^Black, PETG HF/ }));
    await userEvent.click(dialog.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();

    dialog = await openDialog("Teal PETG");
    await userEvent.click(await dialog.findByRole("button", { name: /^Black, PETG HF/ }));
    await userEvent.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(cell("Teal PETG").getByText("Not linked")).toBeInTheDocument();
    expect(screen.queryByText("1 product changed")).toBeNull();
  });

  it("keeps Save off until something new is picked", async () => {
    render(ProductsPage);

    const dialog = await openDialog("White PLA");
    expect(dialog.getByRole("button", { name: "Save" })).toBeDisabled();
    await userEvent.click(
      await dialog.findByRole("button", { name: "Jade White, PLA Basic, Bambu code 10100" }),
    );

    expect(dialog.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("says why the catalog could not be read", async () => {
    catalogApi.getCatalog.mockRejectedValue(new Error("down"));
    render(ProductsPage);

    const dialog = await openDialog("Teal PETG");

    expect(await dialog.findByRole("alert")).toBeInTheDocument();
  });
});
