/** A fake Android bridge for tests: in-memory secure storage, scripted tag reads and QR
 * codes, Back presses, a record of being sent to the background, and a push route whose
 * endpoint changes and tapped notifications the test sends. */

import type {
  BackPress,
  NfcStatus,
  FirebaseClient,
  PhoneBridge,
  PushEndpoint,
  PushRoute,
  TagRead,
} from "#lib/phone/bridge.ts";

export interface FakeBridge extends PhoneBridge {
  storage: Map<string, string>;
  status: NfcStatus;
  qr: (string | null | Error)[];
  /** Deliver a tag to the pending readTag call. */
  tap(read: TagRead): void;
  /** Make the pending readTag call fail, as when a tag is pulled away. */
  fail(): void;
  reads: number;
  /** Press Back, with or without history before the current page. */
  pressBack(canGoBack: boolean): void;
  /** How many times the app was sent to the background. */
  backgrounded: number;
  /** The route for phone notifications: UnifiedPush unless a test says none. */
  route: PushRoute;
  /** The endpoint the route has given, if any. */
  endpoint: PushEndpoint | null;
  /** The VAPID key of each registration, in order. */
  registrations: string[];
  /** How many times the phone unregistered from the route. */
  unregistrations: number;
  /** The Firebase settings the phone was given, in order (null: none). */
  firebaseSettings: (FirebaseClient | null)[];
  /** The route once given Firebase settings, as the google flavor without a distributor. */
  routeWithFirebase: PushRoute | null;
  /** Whether the app restarts when given Firebase settings. */
  restartsForFirebase: boolean;
  /** The route gives a new endpoint (null: it dropped this phone). */
  changeEndpoint(endpoint: PushEndpoint | null): void;
  /** Tap a phone notification for `path`. */
  openNotification(path: string): void;
}

export function fakeBridge(status: NfcStatus = "ready"): FakeBridge {
  let pending: { resolve: (read: TagRead) => void; reject: (error: Error) => void } | null = null;
  const backListeners = new Set<(press: BackPress) => void>();
  const endpointListeners = new Set<(endpoint: PushEndpoint | null) => void>();
  const openListeners = new Set<(path: string) => void>();
  const fake: FakeBridge = {
    app: true,
    appVersion: "app-test",
    storage: new Map(),
    status,
    qr: [],
    reads: 0,
    backgrounded: 0,
    route: "unifiedpush",
    endpoint: null,
    registrations: [],
    unregistrations: 0,
    firebaseSettings: [],
    routeWithFirebase: null,
    restartsForFirebase: false,
    nfcStatus: () => Promise.resolve(fake.status),
    readTag: (_salt, signal) =>
      new Promise<TagRead>((resolve, reject) => {
        fake.reads += 1;
        pending = { resolve, reject };
        signal.addEventListener("abort", () => reject(new Error("aborted")));
      }),
    scanQr: () => {
      const next = fake.qr.shift() ?? null;
      return next instanceof Error ? Promise.reject(next) : Promise.resolve(next);
    },
    secureGet: (key) => Promise.resolve(fake.storage.get(key) ?? null),
    secureSet: (key, value) => {
      fake.storage.set(key, value);
      return Promise.resolve();
    },
    secureRemove: (key) => {
      fake.storage.delete(key);
      return Promise.resolve();
    },
    onBack: (listener) => {
      backListeners.add(listener);
      return () => void backListeners.delete(listener);
    },
    background: () => {
      fake.backgrounded += 1;
      return Promise.resolve();
    },
    pressBack: (canGoBack) => backListeners.forEach((listener) => listener({ canGoBack })),
    pushConfigure: (firebase) => {
      fake.firebaseSettings.push(firebase);
      if (firebase && fake.routeWithFirebase) fake.route = fake.routeWithFirebase;
      return Promise.resolve({ restarting: firebase !== null && fake.restartsForFirebase });
    },
    pushRoute: () => Promise.resolve(fake.route),
    pushRegister: (vapidKey) => {
      fake.registrations.push(vapidKey);
      return Promise.resolve();
    },
    pushUnregister: () => {
      fake.unregistrations += 1;
      fake.endpoint = null;
      return Promise.resolve();
    },
    pushEndpoint: () => Promise.resolve(fake.endpoint),
    onPushEndpoint: (listener) => {
      endpointListeners.add(listener);
      return () => void endpointListeners.delete(listener);
    },
    onNotificationOpen: (listener) => {
      openListeners.add(listener);
      return () => void openListeners.delete(listener);
    },
    changeEndpoint: (endpoint) => {
      fake.endpoint = endpoint;
      endpointListeners.forEach((listener) => listener(endpoint));
    },
    openNotification: (path) => openListeners.forEach((listener) => listener(path)),
    tap: (read) => {
      const current = pending;
      pending = null;
      current?.resolve(read);
    },
    fail: () => {
      const current = pending;
      pending = null;
      current?.reject(new Error("tag lost"));
    },
  };
  return fake;
}

export const PAIRING = {
  url: "https://filament.example.com",
  token: "ftd_abcdefghijklmnopqrstuvwxyz0123456789",
  deviceId: "phone-1",
};

export function tagRead(blocks: string[] = Array(48).fill("00".repeat(16))): TagRead {
  return { tagUid: "01020304", blocks, readOk: true };
}

/** A fake server's answer: `body` is sent as JSON, `text` as it is (a sign-in page, say). */
export interface FakeAnswer {
  status: number;
  body?: unknown;
  text?: string;
  headers?: Record<string, string>;
}

/** A fetch that answers from a route table, recording what was asked. */
export function fakeFetch(
  routes: Record<string, (body: unknown) => FakeAnswer | Error>,
): typeof fetch & { calls: { url: string; init: RequestInit }[] } {
  const calls: { url: string; init: RequestInit }[] = [];
  const fn = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input);
    calls.push({ url, init });
    const key = `${init.method ?? "GET"} ${new URL(url).pathname}`;
    const handler = Object.entries(routes).find(([pattern]) => key.startsWith(pattern))?.[1];
    const answer: FakeAnswer | Error = handler
      ? handler(init.body ? JSON.parse(String(init.body)) : undefined)
      : { status: 404 };
    if (answer instanceof Error) throw answer;
    const text = answer.text ?? (answer.body === undefined ? null : JSON.stringify(answer.body));
    return new Response(text, { status: answer.status, headers: answer.headers });
  }) as typeof fetch & { calls: { url: string; init: RequestInit }[] };
  fn.calls = calls;
  return fn;
}
