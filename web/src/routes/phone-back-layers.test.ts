// The phone's Back button (and swipe-back gesture) with a sheet or dialog open on top of a
// page: Back closes the most recently opened one, the way Escape does, and stays on the page.
import { cleanup, render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { createRawSnippet } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";
import type { Catalog } from "#lib/api/catalog.ts";
import { browserBridge, setBridge } from "#lib/phone/bridge.ts";
import { savePairing } from "#lib/phone/pairing-store.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { fakeBridge, fakeFetch, PAIRING, type FakeBridge } from "../test/fake-bridge.ts";
import { me, spoolRow, summary } from "../test/fixtures.ts";

const nav = vi.hoisted(() => ({
  page: { params: {} as Record<string, string>, url: new URL("https://localhost/") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto }));

const api = vi.hoisted(() => ({
  getInventory: vi.fn(),
  listSpools: vi.fn(),
  getCatalog: vi.fn(),
}));
vi.mock("#lib/api/stock.ts", async (original) => ({
  ...(await original<typeof import("#lib/api/stock.ts")>()),
  getInventory: api.getInventory,
  listSpools: api.listSpools,
}));
vi.mock("#lib/api/catalog.ts", async (original) => ({
  ...(await original<typeof import("#lib/api/catalog.ts")>()),
  getCatalog: api.getCatalog,
}));

const { session } = await import("#lib/auth/session.svelte.ts");
const { phone } = await import("#lib/phone/phone-state.svelte.ts");
const Layout = (await import("./+layout.svelte")).default;
const InventoryPage = (await import("./+page.svelte")).default;
const SpoolsPage = (await import("./spools/+page.svelte")).default;
const CatalogPage = (await import("./catalog/+page.svelte")).default;

const CATALOG: Catalog = {
  lines: [
    {
      uuid: "pla-basic",
      name: "PLA Basic",
      material: "PLA",
      colors: [
        {
          uuid: "var-black",
          name: "Black",
          hexes: ["000000"],
          discontinued: false,
          multi_color: false,
          gradient: false,
          bambu_code: "10101",
          similar: [],
          owned: false,
          owned_products: [],
          linked_none_in_stock: [],
        },
      ],
    },
  ],
  synced: true,
  dataset_version: "2026.11.15",
  last_success_at: "2026-11-15T04:00:00Z",
  cutoff: 10,
  out_of_date: false,
  store_address: "https://us.store.bambulab.com",
};

const children = createRawSnippet(() => ({ render: () => "<p>page content</p>" }));

let native: FakeBridge;
let back: MockInstance<() => void>;

/** The Layout for a paired phone at `path`, signed in as an Editor, past the start screen. */
async function openAt(path: string): Promise<void> {
  await savePairing(PAIRING, "AABB");
  session.user = me("editor");
  session.loaded = true;
  nav.page.url = new URL(path, "https://localhost");
  render(Layout, { children });
  await screen.findByText("page content");
}

beforeEach(() => {
  native = fakeBridge();
  setBridge(native);
  viewport().phone = true;
  back = vi.spyOn(window.history, "back").mockImplementation(() => {});
  api.getInventory.mockResolvedValue([summary()]);
  api.listSpools.mockResolvedValue({ items: [spoolRow()], total: 1, limit: 50, offset: 0 });
  api.getCatalog.mockResolvedValue(CATALOG);
  vi.stubGlobal(
    "fetch",
    fakeFetch({
      "GET /api/v1/devices/provisioning": () => ({ status: 200, body: { kdf_salt: "AABB" } }),
      "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
    }),
  );
});

afterEach(async () => {
  cleanup();
  back.mockRestore();
  setBridge(native);
  await phone.unpair();
  phone.loaded = false;
  session.user = null;
  session.loaded = false;
  setBridge(browserBridge);
  viewport().phone = false;
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});

/** Nothing else happened: no page back, no background. */
function stayed(): void {
  expect(back).not.toHaveBeenCalled();
  expect(native.backgrounded).toBe(0);
}

describe("Back with a layer open", () => {
  it("closes the menu sheet and stays on the page", async () => {
    await openAt("/spools");
    const bar = screen.getByRole("navigation", { name: "App" });
    await userEvent.click(within(bar).getByRole("button", { name: "Menu" }));
    expect(screen.getByRole("dialog", { name: "Menu" })).toBeInTheDocument();

    native.pressBack(true);
    await vi.waitFor(() => expect(screen.queryByRole("dialog", { name: "Menu" })).toBeNull());

    stayed();
    expect(screen.getByText("page content")).toBeInTheDocument();
  });

  it.each([
    ["Inventory", "/", InventoryPage, "Black PLA Basic"],
    ["Spools", "/spools", SpoolsPage, "Showing 1–1 of 1"],
    ["Catalog", "/catalog", CatalogPage, "Black"],
  ])("closes the filter sheet on %s and stays on the list", async (_page, path, Page, shown) => {
    await openAt(path);
    render(Page);
    await screen.findAllByText(shown);
    await userEvent.click(screen.getByRole("button", { name: "Filter" }));
    expect(screen.getByRole("dialog", { name: "Filter" })).toBeInTheDocument();

    native.pressBack(true);
    await vi.waitFor(() => expect(screen.queryByRole("dialog", { name: "Filter" })).toBeNull());

    stayed();
    expect(screen.getAllByText(shown).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Filter" })).toBeInTheDocument();
  });
});
