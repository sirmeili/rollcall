/** The real phone bridge: the Android app's Kotlin plugin, reached through Capacitor.
 *
 * The plugin (android/app/src/main/java/.../FilamentTrackerPlugin.kt) reads tags, scans QR
 * codes and keeps values encrypted with the Android Keystore. The salt goes in; derived keys
 * never come back out. Capacitor's official App plugin reports Back presses and sends the
 * app to the background.
 */

import { App } from "@capacitor/app";
import { Capacitor, registerPlugin, type PluginListenerHandle } from "@capacitor/core";
import { setBridge, type NfcStatus, type PhoneBridge, type TagRead } from "#lib/phone/bridge.ts";

export interface FilamentTrackerPlugin {
  appInfo(): Promise<{ version: string }>;
  nfcStatus(): Promise<{ status: NfcStatus }>;
  readTag(options: { salt: string }): Promise<TagRead>;
  cancelRead(): Promise<void>;
  scanQr(): Promise<{ value: string | null }>;
  secureGet(options: { key: string }): Promise<{ value: string | null }>;
  secureSet(options: { key: string; value: string }): Promise<void>;
  secureRemove(options: { key: string }): Promise<void>;
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
    onBack: (listener) => {
      const handle = app.addListener("backButton", ({ canGoBack }) => listener({ canGoBack }));
      return () => void handle.then((listening) => listening.remove());
    },
    background: () => app.minimizeApp(),
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
