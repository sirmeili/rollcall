import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Catalog, CatalogColor } from "#lib/api/catalog.ts";
import type { ShoppingList } from "#lib/api/shopping.ts";
import { session } from "#lib/auth/session.svelte.ts";
import { setTimeZone } from "#lib/format.ts";
import type { Role } from "#lib/roles.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { fakeFetch, me, product } from "../test/fixtures.ts";
import { added, handItem, handReason, lowItem, shoppingList } from "../test/shopping-fixtures.ts";

const ShoppingListPage = (await import("./shopping-list/+page.svelte")).default;

const BLACK = handItem(1, "Black PLA Basic", [handReason(7, 2), handReason(8, 1, null)]);
const LIST: ShoppingList = shoppingList({ not_in_catalog: [BLACK] });
const AFTER_REMOVE: ShoppingList = shoppingList({
  not_in_catalog: [
    {
      ...handItem(1, "Black PLA Basic", [handReason(8, 1, null)]),
      history: [{ ...added(2), action: "removed_by_hand" }, ...BLACK.history],
    },
  ],
});

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

const CATALOG: Catalog = {
  lines: [
    {
      uuid: "pla-basic",
      name: "PLA Basic",
      material: "PLA",
      colors: [
        color("jade", "Jade White", { bambu_code: "10100" }),
        // Linked to Black PLA Basic already: offered as that product, not again as a color.
        color("black", "Black", { linked_none_in_stock: [{ product_id: 1, name: "Black" }] }),
      ],
    },
  ],
  synced: true,
  dataset_version: "2026.11.15",
  last_success_at: "2026-11-15T04:00:00Z",
  cutoff: 10,
  out_of_date: false,
  store_address: "https://store.example",
};

const PRODUCTS = [
  product({ id: 1, display_name: "Black PLA Basic" }),
  product({ id: 4, display_name: "Red PETG", filament_type: "PETG", color_rgba: "FF0000FF" }),
];

function serve(routes: Record<string, unknown> = {}) {
  const fetch = fakeFetch({
    "GET /shopping-list": LIST,
    "GET /products": PRODUCTS,
    "GET /catalog": CATALOG,
    ...routes,
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function signedInAs(role: Role): void {
  session.user = me(role);
}

function item(name: string): HTMLElement {
  return screen.getByText(name).closest("li") as HTMLElement;
}

beforeEach(() => {
  setTimeZone("UTC");
  vi.useFakeTimers({ now: new Date("2026-11-22T09:00:00Z"), shouldAdvanceTime: true });
  signedInAs("editor");
});

afterEach(() => {
  vi.useRealTimers();
  setTimeZone(undefined);
  session.user = null;
  viewport().phone = false;
  vi.unstubAllGlobals();
});

describe("spools added by hand on the shopping list", () => {
  it("shows each hand-added reason and the item's recent history", async () => {
    serve();
    render(ShoppingListPage);

    await screen.findByText("Black PLA Basic");
    const black = item("Black PLA Basic");
    expect(within(black).getByText("Added by hand by frank · 2 spools")).toBeInTheDocument();
    expect(within(black).getByText("Added by hand · 1 spool")).toBeInTheDocument();
    const history = within(black).getByRole("list", { name: "Recent history" });
    expect(
      within(history)
        .getAllByRole("listitem")
        .map((e) => e.textContent),
    ).toEqual([
      expect.stringContaining("Added 2 spools by hand"),
      expect.stringContaining("Added 1 spool by hand"),
    ]);
    expect(within(history).getByText("frank · Nov 21, 12:00 PM · 0 on order")).toBeInTheDocument();
  });

  it("lets an Editor remove a hand-added reason", async () => {
    const fetch = serve({ "DELETE /shopping-list/hand-reasons/7": AFTER_REMOVE });
    render(ShoppingListPage);

    await screen.findByText("Black PLA Basic");
    await userEvent.click(
      screen.getByRole("button", { name: "Remove Added by hand by frank · 2 spools" }),
    );

    expect(await screen.findByText("Removed 2 spools added by hand")).toBeInTheDocument();
    expect(screen.queryByText("Added by hand by frank · 2 spools")).toBeNull();
    expect(fetch.calls.at(-1)).toEqual({
      method: "DELETE",
      path: "/shopping-list/hand-reasons/7",
      body: undefined,
    });
  });

  it("says when a removal fails", async () => {
    serve({ "DELETE /shopping-list/hand-reasons/7": new Response("{}", { status: 500 }) });
    render(ShoppingListPage);

    await screen.findByText("Black PLA Basic");
    await userEvent.click(
      screen.getByRole("button", { name: "Remove Added by hand by frank · 2 spools" }),
    );

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Added by hand by frank · 2 spools")).toBeInTheDocument();
  });

  it("gives Viewers no Remove", async () => {
    signedInAs("viewer");
    serve();
    render(ShoppingListPage);

    await screen.findByText("Black PLA Basic");
    expect(screen.queryByRole("button", { name: /^Remove/ })).toBeNull();
  });

  it("shows the reasons, Remove and history in a phone row's expanded view", async () => {
    viewport().phone = true;
    serve();
    render(ShoppingListPage);

    await userEvent.click(await screen.findByRole("button", { name: /Black PLA Basic/ }));

    expect(
      screen.getByRole("button", { name: "Remove Added by hand by frank · 2 spools" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Recent history" })).toBeInTheDocument();
  });

  it("shows no history for an item with none", async () => {
    serve({ "GET /shopping-list": shoppingList({ not_in_catalog: [lowItem(2, "Red", 1, 0)] }) });
    render(ShoppingListPage);

    await screen.findByText("Red");
    expect(screen.queryByRole("list", { name: "Recent history" })).toBeNull();
  });
});

describe("Add to shopping list on the list page", () => {
  async function openAdd() {
    render(ShoppingListPage);
    await screen.findByText("Black PLA Basic");
    await userEvent.click(screen.getByRole("button", { name: "Add to shopping list" }));
    return within(await screen.findByRole("form", { name: "Add to shopping list" }));
  }

  it("searches products and catalog colors no product is linked to", async () => {
    serve();
    const form = await openAdd();

    await userEvent.type(form.getByRole("searchbox", { name: "Product or catalog color" }), "pla");

    const options = form.getAllByRole("radio").map((r) => r.closest("label")?.textContent);
    expect(options).toEqual([
      expect.stringContaining("Black PLA Basic"),
      expect.stringContaining("Jade White PLA Basic"),
    ]);
    expect(form.queryByText("Black PLA Basic", { selector: ".oname" })).toBeInTheDocument();
  });

  it("adds a catalog color with a number of spools", async () => {
    const after = shoppingList({
      lines: [
        {
          name: "PLA Basic",
          to_buy: 2,
          items: [
            handItem(9, "Jade White PLA Basic", [handReason(9, 2)], {
              provisional: true,
              from_catalog: true,
            }),
          ],
        },
      ],
      not_in_catalog: [BLACK],
    });
    const fetch = serve({ "POST /shopping-list/hand-reasons": after });
    const form = await openAdd();

    await userEvent.type(form.getByRole("searchbox"), "jade");
    await userEvent.click(form.getByRole("radio", { name: /Jade White PLA Basic/ }));
    const spools = form.getByRole("spinbutton", { name: "Spools" });
    await userEvent.clear(spools);
    await userEvent.type(spools, "2");
    await userEvent.click(form.getByRole("button", { name: "Add" }));

    expect(await screen.findByText("Jade White PLA Basic")).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Add to shopping list" })).toBeNull();
    expect(fetch.calls.at(-1)).toEqual({
      method: "POST",
      path: "/shopping-list/hand-reasons",
      body: { catalog_color: "jade", spools: 2 },
    });
  });

  it("adds a product, one spool unless told otherwise", async () => {
    const fetch = serve({ "POST /shopping-list/hand-reasons": LIST });
    const form = await openAdd();

    await userEvent.type(form.getByRole("searchbox"), "red");
    await userEvent.click(form.getByRole("radio", { name: /Red PETG/ }));
    await userEvent.click(form.getByRole("button", { name: "Add" }));

    await vi.waitFor(() => expect(fetch.calls.at(-1)?.body).toEqual({ product_id: 4, spools: 1 }));
  });

  it("keeps Add off until something is picked and the spools are a whole number", async () => {
    serve();
    const form = await openAdd();

    expect(form.getByRole("button", { name: "Add" })).toBeDisabled();
    await userEvent.type(form.getByRole("searchbox"), "red");
    await userEvent.click(form.getByRole("radio", { name: /Red PETG/ }));
    expect(form.getByRole("button", { name: "Add" })).toBeEnabled();
    await userEvent.clear(form.getByRole("spinbutton", { name: "Spools" }));
    expect(form.getByRole("button", { name: "Add" })).toBeDisabled();
  });

  it("says when nothing matches, and closes on Cancel", async () => {
    serve();
    const form = await openAdd();

    await userEvent.type(form.getByRole("searchbox"), "glow");
    expect(form.getByText('Nothing matches "glow".')).toBeInTheDocument();

    await userEvent.click(form.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("form", { name: "Add to shopping list" })).toBeNull();
  });

  it("says when an addition fails, and keeps the form", async () => {
    serve({ "POST /shopping-list/hand-reasons": new Response("{}", { status: 500 }) });
    const form = await openAdd();

    await userEvent.type(form.getByRole("searchbox"), "red");
    await userEvent.click(form.getByRole("radio", { name: /Red PETG/ }));
    await userEvent.click(form.getByRole("button", { name: "Add" }));

    expect(await form.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "Add to shopping list" })).toBeInTheDocument();
  });

  it("says when what it searches could not be read", async () => {
    serve({ "GET /catalog": new Response("{}", { status: 500 }) });
    const form = await openAdd();

    expect(await form.findByRole("alert")).toBeInTheDocument();
    await userEvent.type(form.getByRole("searchbox"), "red");
    expect(form.getByRole("radio", { name: /Red PETG/ })).toBeInTheDocument();
  });
});
