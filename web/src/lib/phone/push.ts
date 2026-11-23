/** Registering a user's phone for phone notifications, with the signed-in session.
 *
 * On start, on signing in and when provisioning first says this is a user's phone, the phone
 * is given the server's Firebase settings, if any, then registers with its route (a
 * UnifiedPush distributor, else FCM in the google flavor) using the server's VAPID public
 * key, and sends the endpoint the route gave to the server. A new endpoint from the route is sent
 * at once; if the user is signed out then, it is sent on the next sign-in, which sends the
 * current endpoint again. A shared phone never registers. The routes answer from anywhere,
 * so this works away from home (server/README.md, Phone notifications).
 */

import { api, ApiError } from "#lib/api/client.ts";
import type { FirebaseClient, PhoneBridge, PushEndpoint } from "#lib/phone/bridge.ts";

/** How the server sends to an endpoint from a UnifiedPush distributor: RFC 8030 Web Push. */
const WEB_PUSH = "web_push";
/** How the server sends to an FCM token: Google's push service (FCM). */
const FCM = "fcm";

/** What a user's phone registers with: the server's VAPID public key, and Firebase's client
 * settings when the server sends through FCM. */
interface PushConfig {
  vapid_public_key: string;
  firebase?: FirebaseClient | null;
}

export class PhonePush {
  private running: Promise<void> | null = null;
  private again = false;
  private unsubscribe: (() => void) | null = null;

  constructor(
    private readonly native: PhoneBridge,
    private readonly deviceId: string,
    /** Whether this is a user's phone; a shared phone never registers. */
    private readonly userPhone: () => boolean,
    private readonly fetchFn: typeof fetch = fetch,
  ) {}

  /** Follow the route's endpoint changes, and register now. */
  start(): void {
    this.unsubscribe = this.native.onPushEndpoint((endpoint) => void this.changed(endpoint));
    void this.sync();
  }

  stop(): void {
    this.unsubscribe?.();
    this.unsubscribe = null;
  }

  /** Register with the route and send the endpoint, as the signed-in user. Signed out, or
   * with the server out of reach, it does nothing and runs again on the next sign-in or
   * start. One runs at a time; asked meanwhile, it runs once more afterwards. */
  sync(): Promise<void> {
    if (this.running) {
      this.again = true;
      return this.running;
    }
    this.running = (async () => {
      try {
        do {
          this.again = false;
          await this.register();
        } while (this.again);
      } finally {
        this.running = null;
      }
    })();
    return this.running;
  }

  private async register(): Promise<void> {
    if (!this.userPhone()) return;
    let config: PushConfig;
    try {
      config = await api<PushConfig>("/push/config", {}, this.fetchFn);
    } catch {
      return;
    }
    // The google flavor starts Firebase from these, and may restart to use new ones.
    if ((await this.native.pushConfigure(config.firebase ?? null)).restarting) return;
    if ((await this.native.pushRoute()) === "none") return;
    await this.native.pushRegister(config.vapid_public_key);
    const endpoint = await this.native.pushEndpoint();
    if (endpoint) await this.send(endpoint);
  }

  private async changed(endpoint: PushEndpoint | null): Promise<void> {
    if (!this.userPhone()) return;
    if (endpoint) await this.send(endpoint);
    else await this.remove();
  }

  private path(): string {
    return `/push/devices/${encodeURIComponent(this.deviceId)}`;
  }

  /** Send the endpoint. The server refuses a phone that isn't the signed-in user's (404):
   * then this phone stops getting pushes through its route. Other failures wait for the
   * next sign-in or start. */
  private async send(endpoint: PushEndpoint): Promise<void> {
    const body =
      endpoint.route === FCM
        ? { route: FCM, endpoint: endpoint.url }
        : { route: WEB_PUSH, endpoint: endpoint.url, p256dh: endpoint.p256dh, auth: endpoint.auth };
    try {
      await api(this.path(), { method: "PUT", body }, this.fetchFn);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        await this.native.pushUnregister().catch(() => {});
      }
    }
  }

  /** Stop phone notifications on this phone, for Unlink and sign-out: unregister from the
   * route first, so they stop even away from home, then remove the endpoint on the server,
   * best effort. A shared phone has neither. */
  async leave(): Promise<void> {
    if (!this.userPhone()) return;
    await this.native.pushUnregister().catch(() => {});
    await this.remove();
  }

  /** The route dropped this phone: so does the server, best effort. */
  private async remove(): Promise<void> {
    await api(this.path(), { method: "DELETE" }, this.fetchFn).catch(() => {});
  }
}
