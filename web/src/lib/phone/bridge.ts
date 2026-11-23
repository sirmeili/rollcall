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
 * through Google's push service (FCM, "via Google", in the google flavor only), or not at
 * all. */
export type PushRoute = "unifiedpush" | "fcm" | "none";

/** Where a push service delivers this phone's notifications, as the route gave them: a Web
 * Push URL with its keys (base64url), or, for the route `fcm`, an FCM token in `url`. */
export type PushEndpoint =
  { route?: "web_push"; url: string; p256dh: string; auth: string } | { route: "fcm"; url: string };

/** The Firebase client settings the server gives a user's phone when it sends through FCM. */
export interface FirebaseClient {
  project_id: string;
  app_id: string;
  api_key: string;
  sender_id: string;
}

/** Whether Android lets RollCall show notifications: granted, or refused (Android 13's
 * permission refused, or notifications turned off for the app in Android's settings). */
export type PhoneNotificationPermission = "granted" | "denied";

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
  /** Give the phone the server's Firebase settings (null: none), before asking its route.
   * `restarting` when the app restarts itself to use them. */
  pushConfigure(firebase: FirebaseClient | null): Promise<{ restarting: boolean }>;
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
  /** Whether Android lets RollCall show notifications now. */
  notificationPermission(): Promise<PhoneNotificationPermission>;
  /** Ask Android for the permission to show notifications (Android 13 and later; earlier
   * ones have none to ask), and say whether it is granted. */
  requestNotificationPermission(): Promise<PhoneNotificationPermission>;
  /** The name people know the route by, such as the distributor app's ("ntfy"); null when
   * there is no route or no name. */
  pushRouteName(): Promise<string | null>;
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
  pushConfigure: () => Promise.resolve({ restarting: false }),
  pushRoute: () => Promise.resolve("none"),
  pushRegister: notInApp,
  pushUnregister: notInApp,
  pushEndpoint: () => Promise.resolve(null),
  onPushEndpoint: () => () => {},
  onNotificationOpen: () => () => {},
  notificationPermission: () => Promise.resolve("denied"),
  requestNotificationPermission: () => Promise.resolve("denied"),
  pushRouteName: () => Promise.resolve(null),
};

let current: PhoneBridge = browserBridge;

export function bridge(): PhoneBridge {
  return current;
}

export function setBridge(next: PhoneBridge): void {
  current = next;
}
