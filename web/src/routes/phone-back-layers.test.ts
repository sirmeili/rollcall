// The phone's Back button (and swipe-back gesture) with a sheet or dialog open on top of a
// page: Back closes the most recently opened one, the way Escape does, and stays on the page.
import { cleanup, render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { createRawSnippet } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";
import { browserBridge, setBridge } from "#lib/phone/bridge.ts";
import { savePairing } from "#lib/phone/pairing-store.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { fakeBridge, fakeFetch, PAIRING, type FakeBridge } from "../test/fake-bridge.ts";
import { me } from "../test/fixtures.ts";

const nav = vi.hoisted(() => ({
  page: { params: {} as Record<string, string>, url: new URL("https://localhost/") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto }));

const { session } = await import("#lib/auth/session.svelte.ts");
const { phone } = await import("#lib/phone/phone-state.svelte.ts");
const Layout = (await import("./+layout.svelte")).default;

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
});
