import { render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Choice, ShoppingStage } from "#lib/api/requests.ts";
import type { Me } from "#lib/api/types.ts";
import { setTimeZone } from "#lib/format.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { me } from "../test/fixtures.ts";
import { choice, request } from "../test/request-fixtures.ts";

const nav = vi.hoisted(() => ({
  page: { params: { id: "41" } as Record<string, string>, url: new URL("https://localhost/") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto }));

const api = vi.hoisted(() => ({ getRequest: vi.fn() }));
vi.mock("#lib/api/requests.ts", async (original) => ({
  ...(await original<typeof import("#lib/api/requests.ts")>()),
  getRequest: api.getRequest,
}));

const { session } = await import("#lib/auth/session.svelte.ts");
const DetailPage = (await import("./requests/[id]/+page.svelte")).default;

const FRANK = me("admin", { id: 1, username: "frank" });
const SAM = me("viewer", { id: 2, username: "sam", requester: true, has_requests: true });

function signIn(user: Me): void {
  session.user = user;
  session.loaded = true;
}

/** A catalog color choice short of filament, as its requester sees it. */
function jade(shopping: ShoppingStage | null, fields: Partial<Choice> = {}): Choice {
  return choice({ id: 2, name: "Jade White PLA Basic", held: false, shopping, ...fields });
}

function stage(fields: Partial<ShoppingStage> = {}): ShoppingStage {
  return { stage: "on_list", product_id: 31, on_order: 0, need: 1, ...fields };
}

function waiting(choices: Choice[]) {
  return request({ status: "waiting_on_filament", choices });
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"], now: new Date("2026-11-18T15:00:00Z") });
  setTimeZone("UTC");
  viewport().phone = false;
});
afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe("A short choice's shopping list stage", () => {
  it("shows a requester their choice is on the shopping list, linked to its item", async () => {
    signIn(SAM);
    api.getRequest.mockResolvedValue(waiting([jade(stage())]));
    render(DetailPage);

    const link = await screen.findByRole("link", { name: "On the shopping list" });
    expect(link).toHaveAttribute("href", "/shopping-list#shopping-item-31");
  });

  it("shows how many of its spools are ordered when partly ordered", async () => {
    signIn(SAM);
    api.getRequest.mockResolvedValue(
      waiting([jade(stage({ stage: "partly_ordered", on_order: 1, need: 3 }))]),
    );
    render(DetailPage);

    expect(
      await screen.findByRole("link", { name: "Partly ordered (1 of 3 spools ordered)" }),
    ).toHaveAttribute("href", "/shopping-list#shopping-item-31");
  });

  it("shows Ordered once nothing is left to buy", async () => {
    signIn(FRANK);
    api.getRequest.mockResolvedValue(
      waiting([
        jade(stage({ stage: "ordered", on_order: 2, need: 2 }), {
          grams: 300,
          short_g: 300,
          holds: [],
        }),
      ]),
    );
    render(DetailPage);

    expect(await screen.findByRole("link", { name: "Ordered" })).toHaveAttribute(
      "href",
      "/shopping-list#shopping-item-31",
    );
  });

  it("shows nothing once the item is gone", async () => {
    signIn(SAM);
    api.getRequest.mockResolvedValue(waiting([jade(null)]));
    render(DetailPage);

    await screen.findByText("Waiting on filament");
    expect(screen.queryByRole("link", { name: /ordered|shopping list/i })).toBeNull();
  });
});
