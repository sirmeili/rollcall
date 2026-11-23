<script lang="ts">
  // The Phone notifications line on Pairing, on a user's phone: whether they work here and by
  // which route, that Android's permission was refused and how to allow it, or that there is
  // no route and ntfy should be installed; with Send a test notification. Checked again when
  // the app comes back to the front, as after allowing notifications in Android's settings.
  import { bridge } from "#lib/phone/bridge.ts";
  import {
    phoneNotificationStatus,
    sendTestNotification,
    type PhoneNotificationStatus,
    type TestResult,
  } from "#lib/phone/notification-status.ts";

  interface Props {
    deviceId: string;
  }

  let { deviceId }: Props = $props();

  let status = $state<PhoneNotificationStatus | null>(null);
  let sending = $state(false);
  let result = $state<TestResult | null>(null);

  async function check(): Promise<void> {
    status = await phoneNotificationStatus(bridge());
  }

  $effect(() => {
    void check();
    const onVisible = () => {
      if (document.visibilityState === "visible") void check();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  });

  async function sendTest(): Promise<void> {
    sending = true;
    result = null;
    try {
      result = await sendTestNotification(deviceId);
    } finally {
      sending = false;
    }
  }
</script>

<section class="notifications" aria-labelledby="notifications-h">
  <h2 id="notifications-h">Phone notifications</h2>
  {#if status?.state === "working"}
    <p>Phone notifications work on this phone, via {status.via}.</p>
  {:else if status?.state === "refused"}
    <p class="warn">
      RollCall isn't allowed to show notifications on this phone. To allow them, open Android's
      Settings, then Apps, RollCall, Notifications, and turn them on.
    </p>
  {:else if status?.state === "no_route"}
    <p class="warn">
      This phone has no way to get phone notifications. Install ntfy, from F-Droid or Google Play,
      then come back here.
    </p>
  {/if}
  <button type="button" class="small" onclick={sendTest} disabled={sending}
    >Send a test notification</button
  >
  {#if result?.ok}
    <p role="status">{result.message}</p>
  {:else if result}
    <p class="warn" role="alert">{result.message}</p>
  {/if}
</section>

<style>
  .notifications {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  h2,
  p {
    margin: 0;
  }

  h2 {
    font-size: 1rem;
  }

  .small {
    align-self: flex-start;
  }

  .warn {
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--lowbg);
    color: var(--lowtext);
  }
</style>
