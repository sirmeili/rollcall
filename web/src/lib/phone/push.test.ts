import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setApiBase } from "#lib/api/client.ts";
import { browserBridge, setBridge } from "#lib/phone/bridge.ts";
import { saveUserPhone, savePairing } from "#lib/phone/pairing-store.ts";
import { PhoneSession } from "#lib/phone/session.ts";
import {
  fakeBridge,
  fakeFetch,
  PAIRING,
  type FakeAnswer,
  type FakeBridge,
} from "../../test/fake-bridge.ts";

const VAPID = "BVapidPublicKey";
const ENDPOINT = {
  url: "https://ntfy.example.com/upAbc",
  p256dh: "BPhoneKey",
  auth: "phoneAuth",
};
const MOVED = { ...ENDPOINT, url: "https://ntfy.example.com/upMoved" };
const DEVICE_PATH = `/api/v1/push/devices/${PAIRING.deviceId}`;

let native: FakeBridge;

beforeEach(() => {
  vi.useFakeTimers();
  native = fakeBridge();
  setBridge(native);
  setApiBase(PAIRING.url);
});

afterEach(() => {
  setBridge(browserBridge);
  setApiBase("");
  vi.useRealTimers();
});

/** A server where the phone's user is signed in or not, recording each endpoint sent. */
function server(options: { signedIn?: boolean; ownPhone?: boolean } = {}) {
  const state = { signedIn: options.signedIn ?? true, ownPhone: options.ownPhone ?? true };
  const sent: unknown[] = [];
  const removed: number[] = [];
  const guarded = (answer: () => FakeAnswer) => (): FakeAnswer => {
    if (!state.signedIn) return { status: 401, body: { detail: "sign in" } };
    if (!state.ownPhone) return { status: 404, body: { detail: "no such phone of yours" } };
    return answer();
  };
  const fetch = fakeFetch({
    "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
    "GET /api/v1/push/config": () =>
      state.signedIn ? { status: 200, body: { vapid_public_key: VAPID } } : { status: 401 },
    [`PUT ${DEVICE_PATH}`]: (body) =>
      guarded(() => {
        sent.push(body);
        return { status: 200, body: {} };
      })(),
    [`DELETE ${DEVICE_PATH}`]: guarded(() => {
      removed.push(1);
      return { status: 204 };
    }),
  });
  return { state, sent, removed, fetch };
}

async function userPhone(fetch: typeof globalThis.fetch, own = true): Promise<PhoneSession> {
  await savePairing(PAIRING, "AA");
  await saveUserPhone(own);
  const session = (await PhoneSession.open(native, fetch))!;
  session.start();
  await vi.advanceTimersByTimeAsync(0);
  return session;
}

const asSent = (endpoint: typeof ENDPOINT) => ({
  route: "web_push",
  endpoint: endpoint.url,
  p256dh: endpoint.p256dh,
  auth: endpoint.auth,
});

describe("phone notifications on a user's phone", () => {
  it("registers with the server's VAPID key and sends the endpoint, signed in", async () => {
    native.endpoint = ENDPOINT;
    const { sent, fetch } = server();

    const session = await userPhone(fetch);

    expect(native.registrations).toEqual([VAPID]);
    expect(sent).toEqual([asSent(ENDPOINT)]);
    session.stop();
  });

  it("sends the endpoint the route gives after registering", async () => {
    const { sent, fetch } = server();
    const session = await userPhone(fetch);
    expect(sent).toEqual([]);

    native.changeEndpoint(ENDPOINT);
    await vi.advanceTimersByTimeAsync(0);

    expect(sent).toEqual([asSent(ENDPOINT)]);
    session.stop();
  });

  it("registers once signed in, not before", async () => {
    native.endpoint = ENDPOINT;
    const { state, sent, fetch } = server({ signedIn: false });
    const session = await userPhone(fetch);
    expect(native.registrations).toEqual([]);

    state.signedIn = true;
    await session.push.sync();

    expect(native.registrations).toEqual([VAPID]);
    expect(sent).toEqual([asSent(ENDPOINT)]);
    session.stop();
  });

  it("sends a changed endpoint at once", async () => {
    native.endpoint = ENDPOINT;
    const { sent, fetch } = server();
    const session = await userPhone(fetch);

    native.changeEndpoint(MOVED);
    await vi.advanceTimersByTimeAsync(0);

    expect(sent).toEqual([asSent(ENDPOINT), asSent(MOVED)]);
    session.stop();
  });

  it("sends an endpoint changed while signed out once signed in again", async () => {
    native.endpoint = ENDPOINT;
    const { state, sent, fetch } = server();
    const session = await userPhone(fetch);

    state.signedIn = false;
    native.changeEndpoint(MOVED);
    await vi.advanceTimersByTimeAsync(0);
    expect(sent).toEqual([asSent(ENDPOINT)]);

    state.signedIn = true;
    await session.push.sync();

    expect(sent).toEqual([asSent(ENDPOINT), asSent(MOVED)]);
    session.stop();
  });

  it("removes the endpoint from the server when the route drops this phone", async () => {
    native.endpoint = ENDPOINT;
    const { removed, fetch } = server();
    const session = await userPhone(fetch);

    native.changeEndpoint(null);
    await vi.advanceTimersByTimeAsync(0);

    expect(removed).toHaveLength(1);
    session.stop();
  });

  it("unregisters when the server says this isn't the signed-in user's phone", async () => {
    native.endpoint = ENDPOINT;
    const { sent, fetch } = server({ ownPhone: false });

    const session = await userPhone(fetch);

    expect(sent).toEqual([]);
    expect(native.unregistrations).toBe(1);
    session.stop();
  });

  it("registers nothing when the phone has no route", async () => {
    native.route = "none";
    const { fetch } = server();

    const session = await userPhone(fetch);

    expect(native.registrations).toEqual([]);
    // Only the push configuration is read: with Firebase in it, the google flavor may then
    // have a route.
    expect(fetch.calls.filter((call) => call.url.includes("/push/devices/"))).toEqual([]);
    session.stop();
  });

  it("gives the phone no Firebase settings when the server has none", async () => {
    native.endpoint = ENDPOINT;
    const { fetch } = server();

    const session = await userPhone(fetch);

    expect(native.firebaseSettings).toEqual([null]);
    session.stop();
  });

  it("runs one registration at a time, and again if asked meanwhile", async () => {
    native.endpoint = ENDPOINT;
    const { sent, fetch } = server();
    const session = await userPhone(fetch);

    expect(native.registrations).toHaveLength(1); // on start

    // Three asks while one runs: the running one, then one more for the other two.
    await Promise.all([session.push.sync(), session.push.sync(), session.push.sync()]);

    expect(native.registrations).toHaveLength(3);
    expect(sent).toHaveLength(3);
    session.stop();
  });

  it("stops following endpoint changes when the session stops", async () => {
    const { sent, fetch } = server();
    const session = await userPhone(fetch);
    session.stop();

    native.changeEndpoint(ENDPOINT);
    await vi.advanceTimersByTimeAsync(0);

    expect(sent).toEqual([]);
  });
});

describe("phone notifications through Google's push service (FCM)", () => {
  const FIREBASE = {
    project_id: "rollcall-test",
    app_id: "1:123:android:abc",
    api_key: "AIzaKey",
    sender_id: "123",
  };
  const TOKEN = { route: "fcm" as const, url: "fcm-token:abc" };

  function firebaseServer() {
    const sent: unknown[] = [];
    const fetch = fakeFetch({
      "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
      "GET /api/v1/push/config": () => ({
        status: 200,
        body: { vapid_public_key: VAPID, firebase: FIREBASE },
      }),
      [`PUT ${DEVICE_PATH}`]: (body) => {
        sent.push(body);
        return { status: 200, body: {} };
      },
    });
    return { sent, fetch };
  }

  it("gives the phone the server's Firebase settings before choosing the route", async () => {
    // Without a distributor, the google flavor has a route only once Firebase is set up.
    native.route = "none";
    native.routeWithFirebase = "fcm";
    native.endpoint = TOKEN;
    const { sent, fetch } = firebaseServer();

    const session = await userPhone(fetch);

    expect(native.firebaseSettings).toEqual([FIREBASE]);
    expect(native.registrations).toEqual([VAPID]);
    expect(sent).toEqual([{ route: "fcm", endpoint: TOKEN.url }]);
    session.stop();
  });

  it("sends a new FCM token at once", async () => {
    native.route = "fcm";
    const { sent, fetch } = firebaseServer();
    const session = await userPhone(fetch);

    native.changeEndpoint({ route: "fcm", url: "fcm-token:new" });
    await vi.advanceTimersByTimeAsync(0);

    expect(sent).toEqual([{ route: "fcm", endpoint: "fcm-token:new" }]);
    session.stop();
  });

  it("registers nothing while the app restarts for new Firebase settings", async () => {
    native.route = "fcm";
    native.restartsForFirebase = true;
    native.endpoint = TOKEN;
    const { sent, fetch } = firebaseServer();

    const session = await userPhone(fetch);

    expect(native.registrations).toEqual([]);
    expect(sent).toEqual([]);
    session.stop();
  });
});

describe("a shared phone", () => {
  it("never registers, signed in or not", async () => {
    native.endpoint = ENDPOINT;
    const { sent, fetch } = server();
    const session = await userPhone(fetch, false);

    await session.push.sync();
    native.changeEndpoint(MOVED);
    await vi.advanceTimersByTimeAsync(0);

    expect(native.registrations).toEqual([]);
    expect(sent).toEqual([]);
    expect(fetch.calls.some((call) => call.url.includes("/push/"))).toBe(false);
    session.stop();
  });

  it("registers once provisioning says it is a user's phone", async () => {
    native.endpoint = ENDPOINT;
    const { sent, fetch } = server();
    const provisioned = fakeFetch({
      "GET /api/v1/devices/provisioning": () => ({
        status: 200,
        body: { kdf_salt: "AA", access: null, records: true, user_phone: true },
      }),
    });
    const both = (async (input: RequestInfo | URL, init?: RequestInit) =>
      String(input).endsWith("/provisioning")
        ? provisioned(input, init)
        : fetch(input, init)) as typeof globalThis.fetch;

    const session = await userPhone(both, false);
    await vi.advanceTimersByTimeAsync(0);

    expect(native.registrations).toEqual([VAPID]);
    expect(sent).toEqual([asSent(ENDPOINT)]);
    session.stop();
  });
});
