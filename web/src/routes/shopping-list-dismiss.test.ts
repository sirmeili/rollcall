import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ShoppingList } from "#lib/api/shopping.ts";
import { session } from "#lib/auth/session.svelte.ts";
import type { Role } from "#lib/roles.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { fakeFetch, me } from "../test/fixtures.ts";
import { lowItem, shoppingList } from "../test/shopping-fixtures.ts";

const ShoppingListPage = (await import("./shopping-list/+page.svelte")).default;

const RED = lowItem(4, "Red PETG", 1, 0, { filament_type: "PETG" });
const GREY = { ...lowItem(5, "Grey", 2, 0), dismissed_need: 1, new_since_dismissal: 2 };
const BLUE = { ...lowItem(6, "Blue", 1, 0), dismissed_need: 3 };

const LIST: ShoppingList = shoppingList({ not_in_catalog: [GREY, RED], dismissed: [BLUE] });
const AFTER_DISMISS: ShoppingList = shoppingList({
  not_in_catalog: [GREY],
  dismissed: [
    BLUE,
    {
      ...RED,
      dismissed_need: 2,
      history: [{ action: "dismissed", spools: 2, size_g: null, on_order: 0, by: "frank", at: "" }],
    },
  ],
});
const AFTER_BRING_BACK: ShoppingList = shoppingList({
  not_in_catalog: [{ ...BLUE, dismissed_need: null }, GREY, RED],
});

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

async function showDismissed(): Promise<void> {
  await userEvent.click(await screen.findByRole("button", { name: "Dismissed (1)" }));
}

beforeEach(() => signedInAs("editor"));

afterEach(() => {
  session.user = null;
  viewport().phone = false;
  vi.unstubAllGlobals();
});

describe("Dismiss on the shopping list", () => {
  it("lets an Editor dismiss an item, which moves it to Dismissed", async () => {
    const fetch = serve({ "POST /shopping-list/items/4/dismiss": AFTER_DISMISS });
    render(ShoppingListPage);

    await screen.findByText("Red PETG");
    await userEvent.click(within(item("Red PETG")).getByRole("button", { name: "Dismiss" }));

    await vi.waitFor(() => expect(screen.queryByText("Red PETG")).toBeNull());
    expect(fetch.calls.at(-1)).toEqual({
      method: "POST",
      path: "/shopping-list/items/4/dismiss",
      body: undefined,
    });
    expect(screen.getByRole("button", { name: "Dismissed (2)" })).toBeInTheDocument();
  });

  it("marks an item back since it was dismissed with what's new", async () => {
    serve();
    render(ShoppingListPage);

    await screen.findByText("Grey");
    expect(within(item("Grey")).getByText("2 spools more than when dismissed")).toBeInTheDocument();
    expect(within(item("Red PETG")).queryByText(/when dismissed/)).toBeNull();
  });

  it("marks what's new on a phone row too", async () => {
    viewport().phone = true;
    serve();
    render(ShoppingListPage);

    const row = await screen.findByRole("button", { name: /^Grey/ });
    expect(within(row).getByText("2 spools more than when dismissed")).toBeInTheDocument();
  });

  it("says when a dismissal fails", async () => {
    serve({ "POST /shopping-list/items/4/dismiss": new Response("{}", { status: 500 }) });
    render(ShoppingListPage);

    await screen.findByText("Red PETG");
    await userEvent.click(within(item("Red PETG")).getByRole("button", { name: "Dismiss" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Red PETG")).toBeInTheDocument();
  });
});

describe("the Dismissed filter", () => {
  it("lists the dismissed items instead of the list", async () => {
    serve();
    render(ShoppingListPage);

    await showDismissed();

    expect(screen.getByRole("button", { name: "Dismissed (1)" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const dismissed = screen.getByRole("region", { name: "Dismissed" });
    expect(within(dismissed).getByText("Blue")).toBeInTheDocument();
    expect(within(dismissed).getByText("Dismissed at 3 spools needed")).toBeInTheDocument();
    expect(screen.queryByText("Red PETG")).toBeNull();
  });

  it("says when nothing is dismissed", async () => {
    serve({ "GET /shopping-list": shoppingList({ not_in_catalog: [RED] }) });
    render(ShoppingListPage);

    await userEvent.click(await screen.findByRole("button", { name: "Dismissed (0)" }));

    expect(screen.getByText("Nothing is dismissed.")).toBeInTheDocument();
  });

  it("lets an Editor bring an item back", async () => {
    const fetch = serve({ "POST /shopping-list/items/6/bring-back": AFTER_BRING_BACK });
    render(ShoppingListPage);
    await showDismissed();

    await userEvent.click(screen.getByRole("button", { name: "Bring back Blue" }));

    await vi.waitFor(() =>
      expect(fetch.calls.at(-1)).toEqual({
        method: "POST",
        path: "/shopping-list/items/6/bring-back",
        body: undefined,
      }),
    );
    expect(await screen.findByText("Nothing is dismissed.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Dismissed (0)" }));
    expect(screen.getByText("Blue")).toBeInTheDocument();
  });

  it("says when Bring back fails", async () => {
    serve({ "POST /shopping-list/items/6/bring-back": new Response("{}", { status: 500 }) });
    render(ShoppingListPage);
    await showDismissed();

    await userEvent.click(screen.getByRole("button", { name: "Bring back Blue" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("gives Viewers the filter but no Dismiss and no Bring back", async () => {
    signedInAs("viewer");
    serve();
    render(ShoppingListPage);

    await screen.findByText("Red PETG");
    expect(screen.queryByRole("button", { name: "Dismiss" })).toBeNull();
    await showDismissed();
    expect(screen.getByText("Blue")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Bring back/ })).toBeNull();
  });

  it("offers Dismiss in a phone row's expanded view", async () => {
    viewport().phone = true;
    serve();
    render(ShoppingListPage);

    await userEvent.click(await screen.findByRole("button", { name: /^Red PETG/ }));

    expect(screen.getByRole("button", { name: "Dismiss" })).toBeInTheDocument();
  });
});
