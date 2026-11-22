import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ShoppingList } from "#lib/api/shopping.ts";
import { session } from "#lib/auth/session.svelte.ts";
import { setTimeZone } from "#lib/format.ts";
import type { Role } from "#lib/roles.ts";
import { shoppingBadge } from "#lib/shopping-badge.svelte.ts";
import { fakeFetch, me, product } from "../test/fixtures.ts";
import {
  handItem,
  handReason,
  lowItem,
  shoppingList,
  suggestedColor,
  suggestion,
} from "../test/shopping-fixtures.ts";

const ShoppingListPage = (await import("./shopping-list/+page.svelte")).default;

const RED_PETG = product({ id: 4, display_name: "Red PETG", filament_type: "PETG" });
const RED = suggestion(3, { product: RED_PETG, spools: 2 });
const JADE = suggestedColor(5, 3);
const LOW = lowItem(1, "Black PLA Basic", 1, 0);
const LIST: ShoppingList = shoppingList({ suggestions: [RED, JADE], not_in_catalog: [LOW] });

function serve(routes: Record<string, unknown> = {}) {
  const fetch = fakeFetch({
    "GET /shopping-list": LIST,
    "GET /products": [RED_PETG],
    "GET /catalog": { lines: [] },
    ...routes,
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

/** Opens the page as `role`, and gives the Suggestions section. */
async function open(role: Role) {
  session.user = me(role);
  render(ShoppingListPage);
  return within(await screen.findByRole("region", { name: /Suggestions/ }));
}

beforeEach(() => {
  setTimeZone("UTC");
  vi.useFakeTimers({ now: new Date("2026-11-22T09:00:00Z"), shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
  setTimeZone(undefined);
  session.user = null;
  shoppingBadge.count = 0;
  vi.unstubAllGlobals();
});

describe("suggestions on the shopping list", () => {
  it("shows the open suggestions in their own section at the top, to every role", async () => {
    serve();
    const section = await open("viewer");

    const rows = section.getAllByRole("listitem").map((row) => row.textContent);
    expect(rows).toEqual([
      expect.stringContaining("Red PETG"),
      expect.stringContaining("Jade White PLA Basic"),
    ]);
    expect(
      section.getByText("2 spools · PETG · suggested by vic · Nov 21, 12:00 PM"),
    ).toBeInTheDocument();
    expect(section.getByText(/^3 spools · catalog color/)).toBeInTheDocument();
    // Viewers suggest; only Editors and Admins decide.
    expect(section.queryByRole("button", { name: /^(Add|Dismiss) / })).toBeNull();
    // The section comes first, and the items' to buy leave the suggestions out.
    const regions = screen.getAllByRole("region").map((r) => r.textContent ?? "");
    expect(regions[0]).toContain("Suggestions");
    expect(screen.getByRole("region", { name: "Not in the catalog, 2 to buy" })).toBeVisible();
  });

  it("sets the Shopping list link's count from the open suggestions", async () => {
    serve();
    await open("viewer");

    expect(shoppingBadge.count).toBe(2);
  });

  it("shows no section when nothing is suggested", async () => {
    serve({ "GET /shopping-list": shoppingList({ not_in_catalog: [LOW] }) });
    session.user = me("editor");
    render(ShoppingListPage);

    await screen.findByText("Black PLA Basic");
    expect(screen.queryByRole("region", { name: /Suggestions/ })).toBeNull();
  });

  it("shows the suggestions when there is nothing to buy", async () => {
    serve({ "GET /shopping-list": shoppingList({ suggestions: [RED] }) });
    const section = await open("viewer");

    expect(section.getByText("Red PETG")).toBeInTheDocument();
    expect(screen.getByText("Nothing to buy.")).toBeInTheDocument();
  });

  it("names a suggested color the catalog has dropped", async () => {
    const gone = suggestion(6, {
      product: null,
      by: null,
      catalog_color: { uuid: "gone", name: null, line: null, hexes: null, bambu_code: null },
    });
    serve({ "GET /shopping-list": shoppingList({ suggestions: [gone] }) });
    const section = await open("editor");

    expect(section.getByText("A color no longer in the catalog")).toBeInTheDocument();
    expect(
      section.getByText("1 spool · catalog color · suggested · Nov 21, 12:00 PM"),
    ).toBeVisible();
  });

  it("lets an Editor add a suggestion, which becomes a hand-added reason", async () => {
    const after = shoppingList({
      suggestions: [JADE],
      not_in_catalog: [LOW, handItem(4, "Red PETG", [handReason(9, 2)])],
    });
    const fetch = serve({ "POST /shopping-list/suggestions/3/add": after });
    const section = await open("editor");

    await userEvent.click(section.getByRole("button", { name: "Add Red PETG" }));

    expect(await screen.findByText("Added by hand by frank · 2 spools")).toBeInTheDocument();
    expect(section.queryByText("Red PETG")).toBeNull();
    expect(fetch.calls.at(-1)).toEqual({
      method: "POST",
      path: "/shopping-list/suggestions/3/add",
      body: undefined,
    });
    expect(shoppingBadge.count).toBe(1);
  });

  it("lets an Admin dismiss a suggestion", async () => {
    const after = shoppingList({ suggestions: [RED], not_in_catalog: [LOW] });
    const fetch = serve({ "POST /shopping-list/suggestions/5/dismiss": after });
    const section = await open("admin");

    await userEvent.click(section.getByRole("button", { name: "Dismiss Jade White PLA Basic" }));

    await vi.waitFor(() => expect(section.queryByText("Jade White PLA Basic")).toBeNull());
    expect(fetch.calls.at(-1)?.path).toBe("/shopping-list/suggestions/5/dismiss");
    expect(shoppingBadge.count).toBe(1);
  });

  it("says when a decision fails, and keeps the suggestion", async () => {
    serve({ "POST /shopping-list/suggestions/3/add": new Response("{}", { status: 409 }) });
    const section = await open("editor");

    await userEvent.click(section.getByRole("button", { name: "Add Red PETG" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(section.getByText("Red PETG")).toBeInTheDocument();
    expect(section.getByRole("button", { name: "Add Red PETG" })).toBeEnabled();
  });

  it("lets a Viewer suggest from Add to shopping list", async () => {
    const after = shoppingList({ suggestions: [RED, JADE, suggestion(7)] });
    const fetch = serve({ "POST /shopping-list/suggestions": after });
    await open("viewer");

    await userEvent.click(screen.getByRole("button", { name: "Add to shopping list" }));
    const form = within(await screen.findByRole("form", { name: "Add to shopping list" }));
    await userEvent.type(form.getByRole("searchbox"), "red");
    await userEvent.click(form.getByRole("radio", { name: /Red PETG/ }));
    await userEvent.click(form.getByRole("button", { name: "Suggest" }));

    expect(await screen.findByText("Suggested 7")).toBeInTheDocument();
    expect(fetch.calls.at(-1)).toEqual({
      method: "POST",
      path: "/shopping-list/suggestions",
      body: { product_id: 4, spools: 1 },
    });
    expect(shoppingBadge.count).toBe(3);
  });
});
