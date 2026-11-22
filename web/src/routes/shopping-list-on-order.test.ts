import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ShoppingList, ShoppingListItem } from "#lib/api/shopping.ts";
import { session } from "#lib/auth/session.svelte.ts";
import { setTimeZone } from "#lib/format.ts";
import type { Role } from "#lib/roles.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { fakeFetch, me } from "../test/fixtures.ts";
import { added, handItem, handReason, link, shoppingList } from "../test/shopping-fixtures.ts";

const ShoppingListPage = (await import("./shopping-list/+page.svelte")).default;

/** A hand-added item with `onOrder` spools on order. */
function ordered(id: number, name: string, need: number, onOrder: number): ShoppingListItem {
  const item = handItem(id, name, [handReason(id * 10, need)], { catalog_link: link() });
  return { ...item, on_order: onOrder, to_buy: Math.max(need - onOrder, 0) };
}

const BLACK = ordered(1, "Black PLA Basic", 3, 1);
const JADE = ordered(2, "Jade White", 2, 2);
const LIST: ShoppingList = shoppingList({
  lines: [{ name: "PLA Basic", to_buy: 2, items: [BLACK, JADE] }],
});

function afterOrdering(spools: number): ShoppingList {
  const black = {
    ...ordered(1, "Black PLA Basic", 3, 1 + spools),
    history: [
      { ...added(spools), action: "ordered" as const, on_order: 1 + spools },
      ...BLACK.history,
    ],
  };
  return shoppingList({ lines: [{ name: "PLA Basic", to_buy: 0, items: [black, JADE] }] });
}

function serve(routes: Record<string, unknown> = {}) {
  const fetch = fakeFetch({ "GET /shopping-list": LIST, ...routes });
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
  signedInAs("editor");
});

afterEach(() => {
  setTimeZone(undefined);
  session.user = null;
  viewport().phone = false;
  vi.unstubAllGlobals();
});

describe("on order on the shopping list", () => {
  it("shows to buy, then need and on order", async () => {
    serve();
    render(ShoppingListPage);

    await screen.findByText("Black PLA Basic");
    const black = item("Black PLA Basic");
    expect(within(black).getByText("2")).toBeInTheDocument();
    expect(within(black).getByText("3 need · 1 on order")).toBeInTheDocument();
  });

  it("keeps a fully ordered item in its line under an On order label", async () => {
    serve();
    render(ShoppingListPage);

    await screen.findByText("Jade White");
    const onOrder = screen.getByRole("list", { name: "On order" });
    expect(within(onOrder).getByText("Jade White")).toBeInTheDocument();
    expect(within(onOrder).queryByText("Black PLA Basic")).toBeNull();
    expect(screen.getByRole("region", { name: /^PLA Basic/ }).contains(onOrder)).toBe(true);
  });

  it("lets an Editor mark an item Ordered, defaulting to its to buy", async () => {
    const fetch = serve({ "POST /shopping-list/items/1/ordered": afterOrdering(2) });
    render(ShoppingListPage);

    await screen.findByText("Black PLA Basic");
    await userEvent.click(within(item("Black PLA Basic")).getByRole("button", { name: "Ordered" }));
    const form = within(screen.getByRole("form", { name: "Ordered Black PLA Basic" }));
    expect(form.getByRole("spinbutton", { name: "Spools ordered" })).toHaveValue(2);
    await userEvent.click(form.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Ordered 2 spools")).toBeInTheDocument();
    expect(fetch.calls.at(-1)).toEqual({
      method: "POST",
      path: "/shopping-list/items/1/ordered",
      body: { spools: 2 },
    });
    expect(screen.queryByRole("form", { name: "Ordered Black PLA Basic" })).toBeNull();
  });

  it("defaults Ordered to 1 on a fully ordered item", async () => {
    serve();
    render(ShoppingListPage);

    await screen.findByText("Jade White");
    await userEvent.click(within(item("Jade White")).getByRole("button", { name: "Ordered" }));

    const form = within(screen.getByRole("form", { name: "Ordered Jade White" }));
    expect(form.getByRole("spinbutton", { name: "Spools ordered" })).toHaveValue(1);
  });

  it("lets an Editor set on order to any number, 0 included", async () => {
    const fetch = serve({ "PUT /shopping-list/items/1/on-order": LIST });
    render(ShoppingListPage);

    await screen.findByText("Black PLA Basic");
    await userEvent.click(
      within(item("Black PLA Basic")).getByRole("button", { name: "Edit on order" }),
    );
    const form = within(screen.getByRole("form", { name: "Edit on order Black PLA Basic" }));
    const field = form.getByRole("spinbutton", { name: "On order" });
    expect(field).toHaveValue(1);
    await userEvent.clear(field);
    await userEvent.type(field, "0");
    await userEvent.click(form.getByRole("button", { name: "Save" }));

    await vi.waitFor(() =>
      expect(fetch.calls.at(-1)).toEqual({
        method: "PUT",
        path: "/shopping-list/items/1/on-order",
        body: { on_order: 0 },
      }),
    );
  });

  it("refuses a number below 0 or not whole", async () => {
    serve();
    render(ShoppingListPage);

    await screen.findByText("Black PLA Basic");
    await userEvent.click(
      within(item("Black PLA Basic")).getByRole("button", { name: "Edit on order" }),
    );
    const form = within(screen.getByRole("form", { name: "Edit on order Black PLA Basic" }));
    await userEvent.clear(form.getByRole("spinbutton", { name: "On order" }));

    expect(form.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(form.getByText("On order: a whole number, 0 to 999.")).toBeInTheDocument();
  });

  it("says when an order can't be saved, and Cancel closes it", async () => {
    serve({ "POST /shopping-list/items/1/ordered": new Response("{}", { status: 500 }) });
    render(ShoppingListPage);

    await screen.findByText("Black PLA Basic");
    await userEvent.click(within(item("Black PLA Basic")).getByRole("button", { name: "Ordered" }));
    const form = within(screen.getByRole("form", { name: "Ordered Black PLA Basic" }));
    await userEvent.click(form.getByRole("button", { name: "Save" }));

    expect(await form.findByRole("alert")).toBeInTheDocument();
    await userEvent.click(form.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("form", { name: "Ordered Black PLA Basic" })).toBeNull();
  });

  it("gives Viewers no Ordered and no Edit on order", async () => {
    signedInAs("viewer");
    serve();
    render(ShoppingListPage);

    await screen.findByText("Black PLA Basic");
    expect(screen.getByText("3 need · 1 on order")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ordered" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Edit on order" })).toBeNull();
  });

  it("shows need, on order and the actions in a phone row's expanded view", async () => {
    viewport().phone = true;
    serve();
    render(ShoppingListPage);

    await userEvent.click(await screen.findByRole("button", { name: /Black PLA Basic/ }));

    expect(screen.getByText("3 need · 1 on order")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ordered" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "On order" })).toBeInTheDocument();
  });
});
