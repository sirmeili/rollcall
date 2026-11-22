import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Catalog, CatalogColor } from "#lib/api/catalog.ts";
import { session } from "#lib/auth/session.svelte.ts";
import type { Role } from "#lib/roles.ts";
import { fakeFetch, me } from "../test/fixtures.ts";
import { shoppingList } from "../test/shopping-fixtures.ts";

const CatalogPage = (await import("./catalog/+page.svelte")).default;

function color(uuid: string, name: string, hex: string): CatalogColor {
  return {
    uuid,
    name,
    hexes: [hex],
    discontinued: false,
    multi_color: false,
    gradient: false,
    bambu_code: "10100",
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
      colors: [color("jade", "Jade White", "F5F5F0")],
    },
  ],
  synced: true,
  dataset_version: "2026.11.15",
  last_success_at: "2026-11-15T04:00:00Z",
  cutoff: 10,
  out_of_date: false,
  store_address: "https://store.example",
};

function serve(routes: Parameters<typeof fakeFetch>[0] = {}) {
  const fetch = fakeFetch({ "GET /catalog": CATALOG, ...routes });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

/** Opens the Catalog page as `role` and expands Jade White. */
async function expandJade(role: Role) {
  session.user = me(role);
  render(CatalogPage);
  const row = await screen.findByRole("button", { name: /^Jade White #F5F5F0/ });
  await userEvent.click(row);
  return within(document.getElementById(row.getAttribute("aria-controls") ?? "")!);
}

afterEach(() => {
  vi.unstubAllGlobals();
  session.user = null;
});

describe("Add to shopping list on a Catalog color row", () => {
  it("adds a number of spools of the color, beside Find in store", async () => {
    const fetch = serve({ "POST /shopping-list/hand-reasons": shoppingList() });
    const detail = await expandJade("editor");

    expect(detail.getByRole("link", { name: /Find in store/ })).toBeInTheDocument();
    const spools = detail.getByRole("spinbutton", { name: "Spools of Jade White" });
    await userEvent.clear(spools);
    await userEvent.type(spools, "3");
    await userEvent.click(detail.getByRole("button", { name: "Add to shopping list" }));

    expect(await detail.findByRole("status")).toHaveTextContent(
      "Added 3 spools of Jade White to the shopping list.",
    );
    expect(fetch.calls.at(-1)).toEqual({
      method: "POST",
      path: "/shopping-list/hand-reasons",
      body: { catalog_color: "jade", spools: 3 },
    });
  });

  it("keeps the button off until the spools are a whole number", async () => {
    serve();
    const detail = await expandJade("admin");

    await userEvent.clear(detail.getByRole("spinbutton", { name: "Spools of Jade White" }));

    expect(detail.getByRole("button", { name: "Add to shopping list" })).toBeDisabled();
  });

  it("says when the addition fails", async () => {
    serve({ "POST /shopping-list/hand-reasons": new Response("{}", { status: 500 }) });
    const detail = await expandJade("editor");

    await userEvent.click(detail.getByRole("button", { name: "Add to shopping list" }));

    expect(await detail.findByRole("alert")).toBeInTheDocument();
    expect(detail.queryByRole("status")).toBeNull();
  });

  it("is not offered to Viewers", async () => {
    serve();
    const detail = await expandJade("viewer");

    expect(detail.getByRole("link", { name: /Find in store/ })).toBeInTheDocument();
    expect(detail.queryByRole("button", { name: "Add to shopping list" })).toBeNull();
  });
});
