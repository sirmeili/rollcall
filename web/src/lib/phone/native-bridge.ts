/** The real phone bridge: the Android app's Kotlin plugin, reached through Capacitor.
 *
 * The plugin (android/app/src/main/java/.../FilamentTrackerPlugin.kt) reads tags, scans QR
 * codes and keeps values encrypted with the Android Keystore. The salt goes in; derived keys
 * never come back out. It also registers for phone notifications through the phone's route
 * and reports tapped ones. Capacitor's official App plugin reports Back presses and sends the
 * app to the background.
 */

import { App } from "@capacitor/app";
import { Capacitor, registerPlugin, type PluginListenerHandle } from "@capacitor/core";
import {
  setBridge,
  type NfcStatus,
  type FirebaseClient,
  type PhoneBridge,
  type PushEndpoint,
  type PushPermission,
  type PushRoute,
  type TagRead,
} from "#lib/phone/bridge.ts";

export interface FilamentTrackerPlugin {
  appInfo(): Promise<{ version: string }>;
  nfcStatus(): Promise<{ status: NfcStatus }>;
  readTag(options: { salt: string }): Promise<TagRead>;
  cancelRead(): Promise<void>;
  scanQr(): Promise<{ value: string | null }>;
  secureGet(options: { key: string }): Promise<{ value: string | null }>;
  secureSet(options: { key: string; value: string }): Promise<void>;
  secureRemove(options: { key: string }): Promise<void>;
  pushConfigure(options: { firebase: FirebaseClient | null }): Promise<{ restarting?: boolean }>;
  pushRoute(): Promise<{ route: PushRoute }>;
  pushRegister(options: { vapidKey: string }): Promise<void>;
  pushUnregister(): Promise<void>;
  pushEndpoint(): Promise<{ endpoint: PushEndpoint | null }>;
  pushPermission(): Promise<{ permission: PushPermission }>;
  requestPushPermission(): Promise<{ permission: PushPermission }>;
  pushRouteName(): Promise<{ name?: string | null }>;
  addListener(
    eventName: "pushEndpoint",
    listener: (event: { endpoint?: PushEndpoint | null }) => void,
  ): Promise<PluginListenerHandle>;
  addListener(
    eventName: "notificationOpened",
    listener: (event: { path: string }) => void,
  ): Promise<PluginListenerHandle>;
}

/** Stop a plugin listener once it has been added. */
function stopping(handle: Promise<PluginListenerHandle>): () => void {
  return () => void handle.then((listening) => listening.remove());
}

/** The part of Capacitor's App plugin the bridge uses. */
export interface AppPlugin {
  addListener(
    eventName: "backButton",
    listener: (event: { canGoBack: boolean }) => void,
  ): Promise<PluginListenerHandle>;
  minimizeApp(): Promise<void>;
}

function aborted(): Error {
  return new DOMException("The read was cancelled", "AbortError");
}

export function nativeBridge(
  plugin: FilamentTrackerPlugin,
  version: string,
  app: AppPlugin,
): PhoneBridge {
  return {
    app: true,
    appVersion: `app-${version}`,
    nfcStatus: async () => (await plugin.nfcStatus()).status,
    readTag: (saltHex, signal) => {
      if (signal.aborted) return Promise.reject(aborted());
      return new Promise<TagRead>((resolve, reject) => {
        const onAbort = () => {
          reject(aborted());
          void plugin.cancelRead().catch(() => {});
        };
        signal.addEventListener("abort", onAbort, { once: true });
        plugin.readTag({ salt: saltHex }).then(
          (read) => {
            signal.removeEventListener("abort", onAbort);
            resolve({ tagUid: read.tagUid, blocks: read.blocks, readOk: read.readOk });
          },
          (error: unknown) => {
            signal.removeEventListener("abort", onAbort);
            reject(error instanceof Error ? error : new Error("tag read failed"));
          },
        );
      });
    },
    scanQr: async () => (await plugin.scanQr()).value ?? null,
    secureGet: async (key) => (await plugin.secureGet({ key })).value ?? null,
    secureSet: (key, value) => plugin.secureSet({ key, value }),
    secureRemove: (key) => plugin.secureRemove({ key }),
    onBack: (listener) =>
      stopping(app.addListener("backButton", ({ canGoBack }) => listener({ canGoBack }))),
    background: () => app.minimizeApp(),
    pushConfigure: async (firebase) => ({
      restarting: (await plugin.pushConfigure({ firebase })).restarting === true,
    }),
    pushRoute: async () => (await plugin.pushRoute()).route,
    pushRegister: (vapidKey) => plugin.pushRegister({ vapidKey }),
    pushUnregister: () => plugin.pushUnregister(),
    pushEndpoint: async () => (await plugin.pushEndpoint()).endpoint ?? null,
    onPushEndpoint: (listener) =>
      stopping(plugin.addListener("pushEndpoint", ({ endpoint }) => listener(endpoint ?? null))),
    onNotificationOpen: (listener) =>
      stopping(plugin.addListener("notificationOpened", ({ path }) => listener(path))),
    pushPermission: async () => (await plugin.pushPermission()).permission,
    requestPushPermission: async () => (await plugin.requestPushPermission()).permission,
    pushRouteName: async () => (await plugin.pushRouteName()).name ?? null,
  };
}

export interface Platform {
  isNativePlatform(): boolean;
}

/** Inside the Android app, install the native bridge; in a browser, do nothing. */
export async function installNativeBridge(
  platform: Platform = Capacitor,
  plugin: () => FilamentTrackerPlugin = () =>
    registerPlugin<FilamentTrackerPlugin>("FilamentTracker"),
  app: () => AppPlugin = () => App,
): Promise<boolean> {
  if (!platform.isNativePlatform()) return false;
  const native = plugin();
  const { version } = await native.appInfo();
  setBridge(nativeBridge(native, version, app()));
  return true;
}
