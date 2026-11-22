// The phone's Back button (and swipe-back gesture) on Scan with a scan card showing: Back
// closes the card the way Next does, recording nothing before an action is chosen and never
// undoing one that was recorded.
import { cleanup, render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { createRawSnippet } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";
import { browserBridge, setBridge } from "#lib/phone/bridge.ts";
import { savePairing } from "#lib/phone/pairing-store.ts";
import { fakeBridge, fakeFetch, PAIRING, tagRead, type FakeBridge } from "../test/fake-bridge.ts";
import tags from "../test/tags.json";

const nav = vi.hoisted(() => ({
  page: { url: new URL("https://localhost/scan") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto }));

const { session } = await import("#lib/auth/session.svelte.ts");
const { phone } = await import("#lib/phone/phone-state.svelte.ts");
const Layout = (await import("./+layout.svelte")).default;
const ScanPage = (await import("./scan/+page.svelte")).default;

const children = createRawSnippet(() => ({ render: () => "<p>page content</p>" }));
const READY = "Hold a spool to the back of your phone";

let native: FakeBridge;
let back: MockInstance<() => void>;
let server: ReturnType<typeof fakeFetch>;

/** The actions the server was asked to record (every scan but a lookup). */
function recorded(): string[] {
  return server.calls
    .filter((c) => c.url.endsWith("/api/v1/scans"))
    .map((c) => (JSON.parse(String(c.init.body)) as { action: string }).action)
    .filter((action) => action !== "lookup");
}

function undone(): boolean {
  return server.calls.some((c) => c.url.endsWith("/revert"));
}

/** Nothing else happened: no page back, no background. */
function stayed(): void {
  expect(back).not.toHaveBeenCalled();
  expect(native.backgrounded).toBe(0);
}

/** Scan, in the Layout of a paired phone, waiting for a tap. */
async function openScan(): Promise<void> {
  await savePairing(PAIRING, "AABB");
  render(Layout, { children });
  await screen.findByText("page content");
  render(ScanPage);
  await screen.findByText(READY);
}

async function deliveryOn(): Promise<void> {
  await userEvent.click(screen.getByRole("button", { name: "Delivery" }));
  expect(screen.getByText("Ready")).toBeInTheDocument();
}

beforeEach(() => {
  native = fakeBridge();
  setBridge(native);
  nav.goto.mockReset();
  back = vi.spyOn(window.history, "back").mockImplementation(() => {});
  server = fakeFetch({
    "GET /api/v1/devices/provisioning": () => ({ status: 200, body: { kdf_salt: "AABB" } }),
    "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
    "POST /api/v1/scans": (body) => ({
      status: 200,
      body: {
        feedback: "ok",
        event_id: null,
        state: (body as { action: string }).action === "lookup" ? "sealed" : "open",
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
        suggested: "opened",
        placeholder: false,
      },
    }),
    "POST /api/v1/events/": () => ({ status: 200, body: {} }),
  });
  vi.stubGlobal("fetch", server);
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

describe("Back on Scan with a scan card showing", () => {
  it("closes the card before an action is chosen, recording nothing", async () => {
    await openScan();
    native.tap(tagRead(tags[0].blocks));
    await screen.findByRole("article", { name: "Spool" });

    native.pressBack(true);

    expect(await screen.findByText(READY)).toBeInTheDocument();
    expect(screen.queryByRole("article", { name: "Spool" })).toBeNull();
    stayed();
    expect(recorded()).toEqual([]);
  });

  it("closes the card after an action is recorded, keeping the event", async () => {
    await openScan();
    native.tap(tagRead(tags[0].blocks));
    await userEvent.click(await screen.findByRole("button", { name: "Opened" }));
    await screen.findByText("Recorded just now · spool #7");

    native.pressBack(true);

    expect(await screen.findByText(READY)).toBeInTheDocument();
    expect(screen.getByText(/Black PLA Basic · Opened/)).toBeInTheDocument();
    expect(screen.queryByText(/\(undone\)/)).toBeNull();
    stayed();
    expect(recorded()).toEqual(["opened"]);
    expect(undone()).toBe(false);
  });
});

describe("Back on Scan with a scan card showing, unpacking a delivery", () => {
  function deliveryRows(): HTMLElement[] {
    const list = screen.getByRole("list", { name: "Spools in this delivery" });
    return within(list).queryAllByRole("listitem");
  }

  function stillDelivering(): void {
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delivery" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  }

  it("closes the card before an action is chosen, leaving Delivery and its list", async () => {
    await openScan();
    await deliveryOn();
    native.tap(tagRead(tags[0].blocks));
    await screen.findByRole("region", { name: "Scanned spool" });

    native.pressBack(true);

    await vi.waitFor(() =>
      expect(screen.queryByRole("region", { name: "Scanned spool" })).toBeNull(),
    );
    stillDelivering();
    expect(screen.getByText("Spools you scan show up here.")).toBeInTheDocument();
    stayed();
    expect(recorded()).toEqual([]);
  });

  it("closes the card after an action is recorded, keeping it in the list", async () => {
    await openScan();
    await deliveryOn();
    native.tap(tagRead(tags[0].blocks));
    const panel = await screen.findByRole("region", { name: "Scanned spool" });
    await userEvent.click(within(panel).getByRole("button", { name: "Opened" }));
    await screen.findByText("Recorded Opened");

    native.pressBack(true);

    await vi.waitFor(() => expect(screen.queryByText("Recorded Opened")).toBeNull());
    stillDelivering();
    const rows = deliveryRows();
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent("Black PLA Basic");
    expect(within(rows[0]).queryByText("Undone")).toBeNull();
    expect(screen.getByText("0 new · 1 opened")).toBeInTheDocument();
    stayed();
    expect(recorded()).toEqual(["opened"]);
    expect(undone()).toBe(false);
  });
});

describe("Back on Scan at Ready", () => {
  it("goes back a page, or to the background, as before", async () => {
    await openScan();
    native.tap(tagRead(tags[0].blocks));
    await userEvent.click(await screen.findByRole("button", { name: "Opened" }));
    await userEvent.click(await screen.findByRole("button", { name: "Scan next" }));
    await screen.findByText(READY);

    native.pressBack(true);
    expect(back).toHaveBeenCalledOnce();

    native.pressBack(false);
    expect(native.backgrounded).toBe(1);
    expect(screen.getByText(READY)).toBeInTheDocument();
    expect(undone()).toBe(false);
  });
});
