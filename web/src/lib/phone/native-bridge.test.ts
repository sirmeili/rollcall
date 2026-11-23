import { afterEach, describe, expect, it, vi } from "vitest";
import { bridge, browserBridge, setBridge } from "#lib/phone/bridge.ts";
import {
  installNativeBridge,
  nativeBridge,
  type AppPlugin,
  type FilamentTrackerPlugin,
} from "#lib/phone/native-bridge.ts";

const READ = { tagUid: "01020304", blocks: ["00".repeat(16)], readOk: true };
const ENDPOINT = { url: "https://ntfy.example.com/upAbc", p256dh: "BKey", auth: "secret" };

function fakePlugin() {
  let finishRead: { resolve: (r: typeof READ) => void; reject: (e: unknown) => void } | null = null;
  const storage = new Map<string, string>();
  const listeners = new Map<string, Set<(event: never) => void>>();
  const plugin = {
    appInfo: vi.fn(async () => ({ version: "1.0" })),
    nfcStatus: vi.fn(async () => ({ status: "no_mifare" as const })),
    readTag: vi.fn(
      () =>
        new Promise<typeof READ>((resolve, reject) => {
          finishRead = { resolve, reject };
        }),
    ),
    cancelRead: vi.fn(async () => {}),
    scanQr: vi.fn(async () => ({ value: "code" as string | null })),
    secureGet: vi.fn(async ({ key }: { key: string }) => ({ value: storage.get(key) ?? null })),
    secureSet: vi.fn(async ({ key, value }: { key: string; value: string }) => {
      storage.set(key, value);
    }),
    secureRemove: vi.fn(async ({ key }: { key: string }) => {
      storage.delete(key);
    }),
    pushRoute: vi.fn(async () => ({ route: "unifiedpush" as const })),
    pushRegister: vi.fn(async (_options: { vapidKey: string }) => {}),
    pushUnregister: vi.fn(async () => {}),
    pushEndpoint: vi.fn(async () => ({ endpoint: ENDPOINT as typeof ENDPOINT | null })),
    pushPermission: vi.fn(async () => ({ permission: "denied" as "granted" | "denied" })),
    requestPushPermission: vi.fn(async () => ({ permission: "granted" as "granted" | "denied" })),
    pushRouteName: vi.fn(async () => ({ name: "ntfy" as string | null })),
    addListener: vi.fn(async (event: string, listener: (event: never) => void) => {
      const set = listeners.get(event) ?? new Set();
      set.add(listener);
      listeners.set(event, set);
      return { remove: async () => void set.delete(listener) };
    }),
  } satisfies FilamentTrackerPlugin;
  return {
    plugin,
    storage,
    listeners,
    /** Send an event from the plugin to whatever listens for it. */
    emit: (event: string, data: unknown) =>
      listeners.get(event)?.forEach((listener) => listener(data as never)),
    finish: (read: typeof READ) => finishRead?.resolve(read),
    fail: (error: unknown) => finishRead?.reject(error),
  };
}

/** Capacitor's App plugin: Back presses delivered by `press`, and listeners counted. */
function fakeApp() {
  const listeners = new Set<(event: { canGoBack: boolean }) => void>();
  const app = {
    addListener: vi.fn(
      async (_event: "backButton", listener: (e: { canGoBack: boolean }) => void) => {
        listeners.add(listener);
        return { remove: async () => void listeners.delete(listener) };
      },
    ),
    minimizeApp: vi.fn(async () => {}),
  } satisfies AppPlugin;
  return {
    app,
    listeners,
    press: (canGoBack: boolean) => listeners.forEach((listener) => listener({ canGoBack })),
  };
}

afterEach(() => setBridge(browserBridge));

describe("native bridge", () => {
  it("passes the salt in and returns only the read", async () => {
    const fake = fakePlugin();
    const native = nativeBridge(fake.plugin, "1.0", fakeApp().app);

    const read = native.readTag("AABB", new AbortController().signal);
    fake.finish({ ...READ, extra: "ignored" } as typeof READ);

    expect(await read).toEqual(READ);
    expect(fake.plugin.readTag).toHaveBeenCalledWith({ salt: "AABB" });
  });

  it("cancels the native read when the page stops listening", async () => {
    const fake = fakePlugin();
    const native = nativeBridge(fake.plugin, "1.0", fakeApp().app);
    const stop = new AbortController();

    const read = native.readTag("AABB", stop.signal);
    stop.abort();

    await expect(read).rejects.toMatchObject({ name: "AbortError" });
    expect(fake.plugin.cancelRead).toHaveBeenCalledOnce();
    fake.finish(READ); // too late: ignored
  });

  it("does not start a read that was already cancelled", async () => {
    const fake = fakePlugin();
    const stop = new AbortController();
    stop.abort();

    await expect(
      nativeBridge(fake.plugin, "1.0", fakeApp().app).readTag("AA", stop.signal),
    ).rejects.toThrow(/cancelled/);
    expect(fake.plugin.readTag).not.toHaveBeenCalled();
  });

  it("passes a failed read on as an error", async () => {
    const fake = fakePlugin();
    const native = nativeBridge(fake.plugin, "1.0", fakeApp().app);

    const lost = native.readTag("AA", new AbortController().signal);
    fake.fail(new Error("tag read failed"));
    await expect(lost).rejects.toThrow("tag read failed");

    const odd = native.readTag("AA", new AbortController().signal);
    fake.fail("not an error");
    await expect(odd).rejects.toThrow("tag read failed");
  });

  it("ignores a failed cancel", async () => {
    const fake = fakePlugin();
    fake.plugin.cancelRead.mockRejectedValue(new Error("gone"));
    const stop = new AbortController();
    const read = nativeBridge(fake.plugin, "1.0", fakeApp().app).readTag("AA", stop.signal);
    stop.abort();
    await expect(read).rejects.toMatchObject({ name: "AbortError" });
  });

  it("reports NFC status, QR codes and storage from the plugin", async () => {
    const fake = fakePlugin();
    const native = nativeBridge(fake.plugin, "1.0", fakeApp().app);

    expect(native.app).toBe(true);
    expect(native.appVersion).toBe("app-1.0");
    expect(await native.nfcStatus()).toBe("no_mifare");
    expect(await native.scanQr()).toBe("code");
    fake.plugin.scanQr.mockResolvedValue({ value: null });
    expect(await native.scanQr()).toBeNull();
    fake.plugin.scanQr.mockResolvedValue({} as { value: null });
    expect(await native.scanQr()).toBeNull();

    expect(await native.secureGet("pairing")).toBeNull();
    await native.secureSet("pairing", "x");
    expect(await native.secureGet("pairing")).toBe("x");
    await native.secureRemove("pairing");
    expect(fake.storage.size).toBe(0);
    fake.plugin.secureGet.mockResolvedValue({} as { value: null });
    expect(await native.secureGet("pairing")).toBeNull();
  });
});

describe("phone notifications, through the plugin", () => {
  it("reports the route and the current endpoint", async () => {
    const fake = fakePlugin();
    const native = nativeBridge(fake.plugin, "1.0", fakeApp().app);

    expect(await native.pushRoute()).toBe("unifiedpush");
    expect(await native.pushEndpoint()).toEqual(ENDPOINT);
    fake.plugin.pushEndpoint.mockResolvedValue({ endpoint: null });
    expect(await native.pushEndpoint()).toBeNull();
    fake.plugin.pushEndpoint.mockResolvedValue({} as { endpoint: null });
    expect(await native.pushEndpoint()).toBeNull();
    fake.plugin.pushRoute.mockResolvedValue({ route: "none" } as never);
    expect(await native.pushRoute()).toBe("none");
  });

  it("registers with the server's VAPID key, and unregisters", async () => {
    const fake = fakePlugin();
    const native = nativeBridge(fake.plugin, "1.0", fakeApp().app);

    await native.pushRegister("BVapidKey");
    await native.pushUnregister();

    expect(fake.plugin.pushRegister).toHaveBeenCalledWith({ vapidKey: "BVapidKey" });
    expect(fake.plugin.pushUnregister).toHaveBeenCalledOnce();
  });

  it("passes each changed endpoint on, until unsubscribed", async () => {
    const fake = fakePlugin();
    const native = nativeBridge(fake.plugin, "1.0", fakeApp().app);
    const seen: unknown[] = [];

    const stop = native.onPushEndpoint((endpoint) => seen.push(endpoint));
    await vi.waitFor(() => expect(fake.listeners.get("pushEndpoint")?.size).toBe(1));
    fake.emit("pushEndpoint", { endpoint: ENDPOINT });
    fake.emit("pushEndpoint", { endpoint: null });
    fake.emit("pushEndpoint", {});
    stop();
    await vi.waitFor(() => expect(fake.listeners.get("pushEndpoint")?.size).toBe(0));

    expect(seen).toEqual([ENDPOINT, null, null]);
  });

  it("reports and asks for Android's notification permission", async () => {
    const fake = fakePlugin();
    const native = nativeBridge(fake.plugin, "1.0", fakeApp().app);

    expect(await native.pushPermission()).toBe("denied");
    expect(await native.requestPushPermission()).toBe("granted");
    expect(fake.plugin.requestPushPermission).toHaveBeenCalledOnce();
  });

  it("reports the name the route is known by", async () => {
    const fake = fakePlugin();
    const native = nativeBridge(fake.plugin, "1.0", fakeApp().app);

    expect(await native.pushRouteName()).toBe("ntfy");
    fake.plugin.pushRouteName.mockResolvedValue({} as { name: null });
    expect(await native.pushRouteName()).toBeNull();
  });

  it("passes on the page of each tapped notification", async () => {
    const fake = fakePlugin();
    const native = nativeBridge(fake.plugin, "1.0", fakeApp().app);
    const paths: string[] = [];

    const stop = native.onNotificationOpen((path) => paths.push(path));
    await vi.waitFor(() => expect(fake.listeners.get("notificationOpened")?.size).toBe(1));
    fake.emit("notificationOpened", { path: "/requests/7" });
    stop();
    await vi.waitFor(() => expect(fake.listeners.get("notificationOpened")?.size).toBe(0));

    expect(paths).toEqual(["/requests/7"]);
  });
});

describe("Back and the background, through the App plugin", () => {
  it("passes each Back press on, with whether there is history before the page", async () => {
    const app = fakeApp();
    const native = nativeBridge(fakePlugin().plugin, "1.0", app.app);
    const presses: boolean[] = [];

    native.onBack((press) => presses.push(press.canGoBack));
    await vi.waitFor(() => expect(app.listeners.size).toBe(1));
    app.press(true);
    app.press(false);

    expect(app.app.addListener).toHaveBeenCalledWith("backButton", expect.any(Function));
    expect(presses).toEqual([true, false]);
  });

  it("stops listening when unsubscribed", async () => {
    const app = fakeApp();
    const native = nativeBridge(fakePlugin().plugin, "1.0", app.app);
    const presses: boolean[] = [];

    const stop = native.onBack((press) => presses.push(press.canGoBack));
    stop();
    await vi.waitFor(() => expect(app.listeners.size).toBe(0));
    app.press(true);

    expect(presses).toEqual([]);
  });

  it("minimizes the app to send it to the background", async () => {
    const app = fakeApp();
    await nativeBridge(fakePlugin().plugin, "1.0", app.app).background();
    expect(app.app.minimizeApp).toHaveBeenCalledOnce();
  });
});

describe("the browser bridge", () => {
  it("has no route for phone notifications", async () => {
    expect(await browserBridge.pushRoute()).toBe("none");
    expect(await browserBridge.pushEndpoint()).toBeNull();
    await expect(browserBridge.pushRegister("key")).rejects.toThrow(/Android app/);
    await expect(browserBridge.pushUnregister()).rejects.toThrow(/Android app/);
    browserBridge.onPushEndpoint(() => {})();
    browserBridge.onNotificationOpen(() => {})();
    expect(await browserBridge.pushPermission()).toBe("denied");
    expect(await browserBridge.requestPushPermission()).toBe("denied");
    expect(await browserBridge.pushRouteName()).toBeNull();
  });

  it("never reports Back, and does nothing when asked to background", async () => {
    const listener = vi.fn();
    const stop = browserBridge.onBack(listener);
    stop();
    await expect(browserBridge.background()).resolves.toBeUndefined();
    expect(listener).not.toHaveBeenCalled();
  });
});

describe("installing the bridge", () => {
  it("does nothing in a browser", async () => {
    const plugin = vi.fn();
    expect(await installNativeBridge({ isNativePlatform: () => false }, plugin)).toBe(false);
    expect(plugin).not.toHaveBeenCalled();
    expect(bridge()).toBe(browserBridge);
  });

  it("connects to the plugin in the app, with the app's version", async () => {
    const fake = fakePlugin();
    expect(
      await installNativeBridge(
        { isNativePlatform: () => true },
        () => fake.plugin,
        () => fakeApp().app,
      ),
    ).toBe(true);
    expect(bridge().app).toBe(true);
    expect(bridge().appVersion).toBe("app-1.0");
  });

  it("uses Capacitor's App plugin for Back by default", async () => {
    const fake = fakePlugin();
    expect(await installNativeBridge({ isNativePlatform: () => true }, () => fake.plugin)).toBe(
      true,
    );
    expect(bridge().app).toBe(true);
  });

  it("uses Capacitor by default, which is not native under test", async () => {
    expect(await installNativeBridge()).toBe(false);
  });
});
