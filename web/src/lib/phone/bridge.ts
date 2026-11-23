/** What the phone app needs from Android, behind one interface.
 *
 * The Android app (Capacitor, with a Kotlin NFC plugin) installs the real bridge at
 * start-up with `setBridge`. In a browser the default bridge says it is not the app, so the
 * Scan and Pair screens are hidden and nothing native is called. Tests install fakes.
 */

/** Whether this phone can read Bambu tags right now. */
export type NfcStatus = "ready" | "no_nfc" | "nfc_off" | "no_mifare";

/** One tag read, as a scanner sends it: the UID and the 48 data blocks, without trailers. */
export interface TagRead {
  tagUid: string;
  blocks: string[];
  readOk: boolean;
}

/** One press of the phone's Back button or swipe-back gesture. */
export interface BackPress {
  /** Whether the WebView has history before the current page. */
  canGoBack: boolean;
}

/** How this phone gets phone notifications: through a UnifiedPush distributor such as ntfy,
 * or not at all. */
export type PushRoute = "unifiedpush" | "none";

/** Where a push service delivers this phone's notifications, with its Web Push keys
 * (base64url), as the route gave them. */
export interface PushEndpoint {
  url: string;
  p256dh: string;
  auth: string;
}

export interface PhoneBridge {
  /** True only inside the Android app. */
  readonly app: boolean;
  readonly appVersion: string;
  nfcStatus(): Promise<NfcStatus>;
  /** Wait for the next tag and read it with keys derived from `saltHex`, which stays on the phone. */
  readTag(saltHex: string, signal: AbortSignal): Promise<TagRead>;
  /** Scan a QR code with the camera; null if the user backs out. */
  scanQr(): Promise<string | null>;
  /** Encrypted storage (the Android Keystore in the app). */
  secureGet(key: string): Promise<string | null>;
  secureSet(key: string, value: string): Promise<void>;
  secureRemove(key: string): Promise<void>;
  /** Call `listener` on each Back press, until the returned function is called. While
   * anything listens, Back no longer closes the app on its own. */
  onBack(listener: (press: BackPress) => void): () => void;
  /** Send the app to the background, keeping it running (not finishing it). */
  background(): Promise<void>;
  /** The route this phone would get phone notifications by. */
  pushRoute(): Promise<PushRoute>;
  /** Register with the route, for pushes signed with the server's VAPID public key. The
   * endpoint arrives later, through `onPushEndpoint`. */
  pushRegister(vapidKey: string): Promise<void>;
  /** Stop getting phone notifications through the route. */
  pushUnregister(): Promise<void>;
  /** The endpoint the route last gave, or null when not registered. */
  pushEndpoint(): Promise<PushEndpoint | null>;
  /** Call `listener` each time the route gives a new endpoint, or null when it drops this
   * phone, until the returned function is called. */
  onPushEndpoint(listener: (endpoint: PushEndpoint | null) => void): () => void;
  /** Call `listener` with the page of each tapped phone notification, including the one
   * that opened the app. */
  onNotificationOpen(listener: (path: string) => void): () => void;
}

function notInApp(): Promise<never> {
  return Promise.reject(new Error("Only available in the Android app"));
}

export const browserBridge: PhoneBridge = {
  app: false,
  appVersion: "web",
  nfcStatus: () => Promise.resolve("no_nfc"),
  readTag: notInApp,
  scanQr: notInApp,
  secureGet: notInApp,
  secureSet: notInApp,
  secureRemove: notInApp,
  // A browser's Back is its own: never reported, and there is no background to go to.
  onBack: () => () => {},
  background: () => Promise.resolve(),
  // A browser gets no phone notifications.
  pushRoute: () => Promise.resolve("none"),
  pushRegister: notInApp,
  pushUnregister: notInApp,
  pushEndpoint: () => Promise.resolve(null),
  onPushEndpoint: () => () => {},
  onNotificationOpen: () => () => {},
};

let current: PhoneBridge = browserBridge;

export function bridge(): PhoneBridge {
  return current;
}

export function setBridge(next: PhoneBridge): void {
  current = next;
}
