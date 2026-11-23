// Phone notifications in the phone app: registering once signed in, and opening the page of
// a tapped notification.
import { cleanup, render, waitFor } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Me } from "#lib/api/types.ts";
import { browserBridge, setBridge } from "#lib/phone/bridge.ts";
import { savePairing, saveUserPhone } from "#lib/phone/pairing-store.ts";
import { fakeBridge, fakeFetch, PAIRING, type FakeBridge } from "../test/fake-bridge.ts";
import { me } from "../test/fixtures.ts";

const nav = vi.hoisted(() => ({
  page: { url: new URL("https://localhost/") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto, beforeNavigate: vi.fn() }));

const { session } = await import("#lib/auth/session.svelte.ts");
const { phone } = await import("#lib/phone/phone-state.svelte.ts");
const Layout = (await import("./+layout.svelte")).default;

const children = createRawSnippet(() => ({ render: () => "<p>page content</p>" }));
const BOB = me("viewer", { id: 2, username: "bob" });
const VAPID = "BVapidPublicKey";
const ENDPOINT = { url: "https://ntfy.example.com/upAbc", p256dh: "BKey", auth: "secret" };

let native: FakeBridge;
let serverSignedIn: boolean;
let sent: unknown[];

function at(path: string): void {
  nav.page.url = new URL(path, "https://localhost");
}

beforeEach(async () => {
  native = fakeBridge();
  native.endpoint = ENDPOINT;
  setBridge(native);
  nav.goto.mockReset();
  serverSignedIn = false;
  sent = [];
  vi.stubGlobal(
    "fetch",
    fakeFetch({
      "GET /api/v1/auth/me": () =>
        serverSignedIn ? { status: 200, body: BOB } : { status: 401, body: { detail: "no" } },
      "GET /api/v1/setup": () => ({ status: 200, body: { open: false } }),
      "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
      "GET /api/v1/devices/provisioning": () => ({
        status: 200,
        body: { kdf_salt: "AA", access: null, records: false, user_phone: true },
      }),
      "GET /api/v1/push/config": () =>
        serverSignedIn ? { status: 200, body: { vapid_public_key: VAPID } } : { status: 401 },
      [`PUT /api/v1/push/devices/${PAIRING.deviceId}`]: (body) => {
        if (!serverSignedIn) return { status: 401 };
        sent.push(body);
        return { status: 200, body: {} };
      },
    }),
  );
  await savePairing(PAIRING, "AA");
  await saveUserPhone(true);
});

afterEach(async () => {
  cleanup();
  setBridge(native);
  await phone.unpair();
  phone.loaded = false;
  session.user = null;
  session.loaded = false;
  session.expired = false;
  setBridge(browserBridge);
  vi.unstubAllGlobals();
});

function signIn(user: Me): void {
  serverSignedIn = true;
  session.user = user;
  session.loaded = true;
}

describe("registering a user's phone", () => {
  it("registers and sends its endpoint after signing in", async () => {
    at("/scan");
    await phone.load();
    render(Layout, { children });
    await waitFor(() => expect(phone.reach).toBe("online"));
    expect(native.registrations).toEqual([]);

    signIn(BOB);

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(native.registrations).toContain(VAPID);
    expect(sent[0]).toEqual({
      route: "web_push",
      endpoint: ENDPOINT.url,
      p256dh: ENDPOINT.p256dh,
      auth: ENDPOINT.auth,
    });
  });
});

describe("tapping a phone notification", () => {
  it("opens its page", async () => {
    at("/scan");
    await phone.load();
    render(Layout, { children });

    native.openNotification("/requests/7");

    await waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/requests/7"));
  });

  it("opens only pages of this app", async () => {
    at("/scan");
    await phone.load();
    render(Layout, { children });

    native.openNotification("//evil.example.com/x");

    await waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/"));
    expect(nav.goto).not.toHaveBeenCalledWith("//evil.example.com/x");
  });

  it("signs in first when signed out, then opens the page", async () => {
    at("/scan");
    await phone.load();
    render(Layout, { children });
    native.openNotification("/requests/7");
    await waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/requests/7"));
    cleanup();

    // The page opened: signed out, the app asks to sign in and comes back to it.
    nav.goto.mockReset();
    at("/requests/7");
    render(Layout, { children });

    await waitFor(() =>
      expect(nav.goto).toHaveBeenCalledWith("/login?next=%2Frequests%2F7", { replaceState: true }),
    );
  });
});
