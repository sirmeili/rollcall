// The edges of phone notifications in the phone app: Android's notification permission,
// asked once; the Phone notifications line and its test button on Pairing; and Unlink and
// sign-out stopping phone notifications before the pairing or sign-in is forgotten.
import { cleanup, render, screen, waitFor, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Me } from "#lib/api/types.ts";
import { browserBridge, setBridge } from "#lib/phone/bridge.ts";
import { savePairing, saveServer, saveUserPhone } from "#lib/phone/pairing-store.ts";
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
const PairPage = (await import("./pair/+page.svelte")).default;
const AccountPage = (await import("./account/+page.svelte")).default;

const BOB = me("viewer", { id: 2, username: "bob" });
const VAPID = "BVapidPublicKey";
const ENDPOINT = { url: "https://ntfy.example.com/upAbc", p256dh: "BKey", auth: "secret" };

let native: FakeBridge;
let server: ReturnType<typeof fakeFetch>;
/** Whether provisioning says this is a user's phone. */
let userPhone: boolean;
/** What the phone did, in order: unregistering from its route, and the requests that stop
 * phone notifications and end its sign-in or pairing. */
let order: string[];
/** Whether the server answers. */
let serverUp: boolean;
/** The server's answer to Send a test notification. */
let testAnswer: { status: number; body?: unknown } | Error;

function signIn(user: Me): void {
  session.user = user;
  session.loaded = true;
}

beforeEach(() => {
  native = fakeBridge();
  native.endpoint = ENDPOINT;
  native.permission = "denied";
  setBridge(native);
  nav.goto.mockReset();
  userPhone = true;
  order = [];
  serverUp = true;
  const unregister = native.pushUnregister;
  native.pushUnregister = () => {
    order.push("unregister");
    return unregister();
  };
  const answer = (step: string, status: number) => () => {
    order.push(step);
    return serverUp ? { status } : new TypeError("down");
  };
  testAnswer = {
    status: 200,
    body: { ok: true, message: "Sent a test notification to this phone." },
  };
  server = fakeFetch({
    [`POST /api/v1/push/devices/${PAIRING.deviceId}/test`]: () => testAnswer,
    [`DELETE /api/v1/push/devices/${PAIRING.deviceId}`]: answer("remove endpoint", 204),
    "POST /api/v1/auth/logout": answer("sign out", 204),
    "POST /api/v1/devices/unlink": answer("revoke token", 204),
    "POST /api/v1/devices/mine": () => ({
      status: 201,
      body: { id: PAIRING.deviceId, token: PAIRING.token },
    }),
    "GET /api/v1/devices/provisioning": () => ({
      status: 200,
      body: { kdf_salt: "AA", access: null, records: true, user_phone: userPhone },
    }),
    "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
    "GET /api/v1/push/config": () => ({ status: 200, body: { vapid_public_key: VAPID } }),
    "PUT /api/v1/push/devices/": () => ({ status: 200, body: {} }),
  });
  vi.stubGlobal("fetch", server);
});

afterEach(async () => {
  cleanup();
  setBridge(native);
  await phone.unpair();
  phone.loaded = false;
  session.user = null;
  session.loaded = false;
  setBridge(browserBridge);
  vi.unstubAllGlobals();
});

/** Close the app, and open it again. */
async function reopen(): Promise<void> {
  phone.session?.stop();
  phone.session = null;
  phone.loaded = false;
  await phone.load();
}

describe("Android's notification permission", () => {
  it("is asked once, after signing in on a new phone", async () => {
    await saveServer(PAIRING.url);
    await phone.load();
    signIn(BOB);

    await phone.setUp();

    await vi.waitFor(() => expect(native.permissionRequests).toBe(1));
    await reopen();
    await vi.waitFor(() => expect(phone.reach).toBe("online"));
    expect(native.permissionRequests).toBe(1);
  });

  it("is asked once on the first open of a phone set up before this update", async () => {
    await savePairing(PAIRING, "AA");
    await saveUserPhone(true);

    await phone.load();

    await vi.waitFor(() => expect(native.permissionRequests).toBe(1));
    await reopen();
    await vi.waitFor(() => expect(phone.reach).toBe("online"));
    expect(native.permissionRequests).toBe(1);
  });

  it("is asked once the server first says an updated phone is a user's phone", async () => {
    await savePairing(PAIRING, "AA");

    await phone.load();

    await vi.waitFor(() => expect(native.permissionRequests).toBe(1));
  });

  it("is never asked on a shared phone", async () => {
    userPhone = false;
    await savePairing(PAIRING, "AA");

    await phone.load();

    await vi.waitFor(() => expect(phone.reach).toBe("online"));
    await vi.waitFor(() =>
      expect(server.calls.some((c) => c.url.includes("provisioning"))).toBe(true),
    );
    expect(native.permissionRequests).toBe(0);
  });

  it("isn't asked when notifications are already allowed", async () => {
    native.permission = "granted";
    await savePairing(PAIRING, "AA");
    await saveUserPhone(true);

    await phone.load();
    await vi.waitFor(() => expect(phone.reach).toBe("online"));

    expect(native.permissionRequests).toBe(0);
  });

  it("refused, changes no setting", async () => {
    native.permissionAnswer = "denied";
    await savePairing(PAIRING, "AA");
    await saveUserPhone(true);
    signIn(BOB);

    await phone.load();
    await vi.waitFor(() => expect(native.permissionRequests).toBe(1));
    await vi.waitFor(() => expect(native.registrations).toEqual([VAPID]));

    expect(server.calls.filter((c) => c.url.includes("/account"))).toEqual([]);
  });
});

describe("Pairing on a shared phone", () => {
  it("has no Phone notifications line", async () => {
    userPhone = false;
    await savePairing(PAIRING, "AA");
    await phone.load();
    render(PairPage);

    expect(screen.getByRole("heading", { name: "Pairing" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Phone notifications" })).toBeNull();
  });
});

describe("the Phone notifications line on Pairing", () => {
  beforeEach(async () => {
    native.permission = "granted";
    await savePairing(PAIRING, "AA");
    await saveUserPhone(true);
    await phone.load();
    signIn(BOB);
  });

  function line(): HTMLElement {
    return screen.getByRole("region", { name: "Phone notifications" });
  }

  it("says they work here, and by which route", async () => {
    render(PairPage);

    await waitFor(() =>
      expect(line()).toHaveTextContent("Phone notifications work on this phone, via ntfy."),
    );
  });

  it("names the route by its kind when the phone gives no name", async () => {
    native.routeName = "";
    native.pushRouteName = () => Promise.resolve(null);
    render(PairPage);

    await waitFor(() => expect(line()).toHaveTextContent("via UnifiedPush."));
  });

  it("says via Google for Google's push service", async () => {
    native.route = "fcm";
    native.pushRouteName = () => Promise.resolve(null);
    render(PairPage);

    await waitFor(() =>
      expect(line()).toHaveTextContent("Phone notifications work on this phone, via Google."),
    );
  });

  it("says the permission was refused, and how to allow it", async () => {
    native.permission = "denied";
    render(PairPage);

    await waitFor(() => expect(line()).toHaveTextContent("isn't allowed to show notifications"));
    expect(line()).toHaveTextContent("Android's Settings");
  });

  it("says to install ntfy when there is no route", async () => {
    native.route = "none";
    render(PairPage);

    await waitFor(() => expect(line()).toHaveTextContent("no way to get phone notifications"));
    expect(line()).toHaveTextContent("Install ntfy");
  });

  it("checks again when the app comes back to the front", async () => {
    native.permission = "denied";
    render(PairPage);
    await waitFor(() => expect(line()).toHaveTextContent("isn't allowed"));

    native.permission = "granted";
    document.dispatchEvent(new Event("visibilitychange"));

    await waitFor(() => expect(line()).toHaveTextContent("work on this phone, via ntfy."));
  });

  it("sends a test notification through the server's test route", async () => {
    render(PairPage);

    await userEvent.click(within(line()).getByRole("button", { name: "Send a test notification" }));

    await waitFor(() =>
      expect(within(line()).getByRole("status")).toHaveTextContent(
        "Sent a test notification to this phone.",
      ),
    );
    const call = server.calls.find((c) => c.url.endsWith("/test"))!;
    expect(call.url).toBe(`${PAIRING.url}/api/v1/push/devices/${PAIRING.deviceId}/test`);
    expect(call.init.method).toBe("POST");
  });

  it("says why a test notification wasn't sent", async () => {
    render(PairPage);
    const send = within(line()).getByRole("button", { name: "Send a test notification" });

    testAnswer = { status: 200, body: { ok: false, message: "The push service refused it." } };
    await userEvent.click(send);
    await waitFor(() =>
      expect(within(line()).getByRole("alert")).toHaveTextContent("The push service refused it."),
    );

    testAnswer = {
      status: 409,
      body: { detail: "This phone isn't registered for phone notifications." },
    };
    await userEvent.click(send);
    await waitFor(() =>
      expect(within(line()).getByRole("alert")).toHaveTextContent("isn't registered"),
    );

    testAnswer = {
      status: 429,
      body: { detail: "Wait a few seconds before sending another test notification." },
    };
    await userEvent.click(send);
    await waitFor(() =>
      expect(within(line()).getByRole("alert")).toHaveTextContent("Wait a few seconds"),
    );

    testAnswer = new TypeError("down");
    await userEvent.click(send);
    await waitFor(() =>
      expect(within(line()).getByRole("alert")).toHaveTextContent("Cannot reach the server."),
    );
  });
});

describe("Unlink and sign-out", () => {
  async function setUp(user: boolean): Promise<void> {
    userPhone = user;
    await savePairing(PAIRING, "AA");
    await saveUserPhone(user);
    await phone.load();
    signIn(BOB);
  }

  async function unlink(): Promise<void> {
    render(PairPage);
    await userEvent.click(screen.getByRole("button", { name: "Unlink this phone" }));
    const confirm = screen.getByRole("group", { name: "Confirm" });
    await userEvent.click(within(confirm).getByRole("button", { name: "Unlink this phone" }));
    await waitFor(() => expect(phone.paired).toBe(false));
  }

  it("Unlink unregisters first, then removes the endpoint, then forgets the pairing", async () => {
    await setUp(true);

    await unlink();

    expect(order).toEqual(["unregister", "remove endpoint", "sign out", "revoke token"]);
    expect(native.storage.get("pairing")).toBeUndefined();
    const remove = server.calls.find((c) => c.init.method === "DELETE")!;
    expect(remove.url).toBe(`${PAIRING.url}/api/v1/push/devices/${PAIRING.deviceId}`);
  });

  it("Unlink away from the server still unregisters and forgets the pairing", async () => {
    await setUp(true);
    serverUp = false;

    await unlink();

    expect(order).toEqual(["unregister", "remove endpoint", "sign out", "revoke token"]);
    expect(native.unregistrations).toBe(1);
    expect(native.storage.get("pairing")).toBeUndefined();
  });

  it("sign-out unregisters first, then removes the endpoint, then signs out", async () => {
    await setUp(true);
    render(AccountPage);

    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/login", { replaceState: true }));
    expect(order).toEqual(["unregister", "remove endpoint", "sign out"]);
    expect(phone.paired).toBe(true);
  });

  it("on a shared phone, touch no route", async () => {
    await setUp(false);

    await unlink();

    expect(order).toEqual(["sign out", "revoke token"]);
  });
});
