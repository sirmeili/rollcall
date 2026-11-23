// The phone's Back button (and swipe-back gesture), pressed through the fake bridge.
import { cleanup, render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { createRawSnippet } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";
import { browserBridge, setBridge } from "#lib/phone/bridge.ts";
import { saveOpenOn, savePairing } from "#lib/phone/pairing-store.ts";
import { fakeBridge, fakeFetch, PAIRING, tagRead, type FakeBridge } from "../test/fake-bridge.ts";
import { me } from "../test/fixtures.ts";
import tags from "../test/tags.json";

const nav = vi.hoisted(() => ({
  page: { url: new URL("https://localhost/") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto, beforeNavigate: vi.fn() }));

const { session } = await import("#lib/auth/session.svelte.ts");
const { phone } = await import("#lib/phone/phone-state.svelte.ts");
const Layout = (await import("./+layout.svelte")).default;
const ScanPage = (await import("./scan/+page.svelte")).default;

const children = createRawSnippet(() => ({ render: () => "<p>page content</p>" }));

let native: FakeBridge;
let back: MockInstance<() => void>;

function at(path: string): void {
  nav.page.url = new URL(path, "https://localhost");
}

/** The Layout for a paired phone at `path`, past the start screen. */
async function openAt(path: string): Promise<void> {
  await savePairing(PAIRING, "AABB");
  at(path);
  render(Layout, { children });
  await screen.findByText("page content");
}

beforeEach(() => {
  native = fakeBridge();
  setBridge(native);
  nav.goto.mockReset();
  back = vi.spyOn(window.history, "back").mockImplementation(() => {});
  vi.stubGlobal(
    "fetch",
    fakeFetch({
      "GET /api/v1/devices/provisioning": () => ({ status: 200, body: { kdf_salt: "AABB" } }),
      "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
      "POST /api/v1/scans": (body) => ({
        status: 200,
        body: {
          feedback: "ok",
          event_id: null,
          state: "sealed",
          product: {
            id: 1,
            display_name: "Black PLA Basic",
            filament_type: "PLA",
            color_rgba: "000000FF",
            material_id: "GFA00",
            variant_id: "A00-K00",
          },
          spool: {
            id: 7,
            state: "sealed",
            received_at: "2026-10-12T10:00:00Z",
            opened_at: null,
            emptied_at: null,
            remaining_pct: null,
          },
          actions: (body as { action: string }).action === "lookup" ? ["opened", "cancel"] : [],
          suggested: null,
          placeholder: false,
        },
      }),
    }),
  );
});

afterEach(async () => {
  cleanup();
  back.mockRestore();
  phone.delivery.clear();
  phone.delivery.on = false;
  setBridge(native);
  await phone.unpair();
  phone.loaded = false;
  session.user = null;
  session.loaded = false;
  setBridge(browserBridge);
  vi.unstubAllGlobals();
});

describe("Back in the phone app", () => {
  it("goes back a page when there is history before it", async () => {
    session.user = me("viewer");
    session.loaded = true;
    await openAt("/spools/7");

    native.pressBack(true);

    expect(back).toHaveBeenCalledOnce();
    expect(native.backgrounded).toBe(0);
  });

  it("goes back a page from Scan or Inventory reached with history before it", async () => {
    session.user = me("viewer");
    session.loaded = true;
    await openAt("/scan");
    native.pressBack(true);
    cleanup();

    at("/inventory");
    render(Layout, { children });
    await screen.findByText("page content");
    native.pressBack(true);

    expect(back).toHaveBeenCalledTimes(2);
    expect(native.backgrounded).toBe(0);
  });

  it("sends the app to the background from the opening screen, keeping the page", async () => {
    await saveOpenOn("stock");
    session.user = me("viewer");
    session.loaded = true;
    await openAt("/inventory");

    native.pressBack(false);

    expect(native.backgrounded).toBe(1);
    expect(back).not.toHaveBeenCalled();
    expect(screen.getByText("page content")).toBeInTheDocument();
  });

  it("keeps a Delivery and its list when Scan goes to the background", async () => {
    await openAt("/scan");
    render(ScanPage);
    await screen.findByText("Hold a spool to the back of your phone");
    await userEvent.click(screen.getByRole("button", { name: "Delivery" }));
    native.tap(tagRead(tags[0].blocks));
    const panel = await screen.findByRole("region", { name: "Scanned spool" });
    await userEvent.click(within(panel).getByRole("button", { name: "Opened" }));
    await screen.findByText("Recorded Opened");
    await userEvent.click(screen.getByRole("button", { name: "Scan next" }));

    native.pressBack(false);

    expect(native.backgrounded).toBe(1);
    expect(screen.getByRole("button", { name: "Delivery" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const list = screen.getByRole("list", { name: "Spools in this delivery" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);
  });

  it("sends the app to the background from Pairing on a phone not yet set up", async () => {
    at("/pair");
    render(Layout, { children });
    await screen.findByText("page content");

    native.pressBack(false);

    expect(native.backgrounded).toBe(1);
    expect(back).not.toHaveBeenCalled();
  });

  it("does nothing while the start screen shows", async () => {
    await savePairing(PAIRING, "AABB");
    at("/scan");
    render(Layout, { children });
    expect(screen.getByRole("img", { name: /^Roll Call/ })).toBeInTheDocument();

    native.pressBack(true);
    native.pressBack(false);

    expect(back).not.toHaveBeenCalled();
    expect(native.backgrounded).toBe(0);
    expect(await screen.findByText("page content")).toBeInTheDocument();
  });

  it("stops listening once the app is closed down", async () => {
    await openAt("/scan");
    cleanup();

    native.pressBack(false);

    expect(native.backgrounded).toBe(0);
  });
});
