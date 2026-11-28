<script lang="ts">
  /** Which release the server runs, for everyone signed in; in the phone app also this app's,
   * with a note when the two differ (ADR-0025). The note blocks nothing. */
  import { serverVersion } from "#lib/api/health.ts";
  import { bridge } from "#lib/phone/bridge.ts";
  import { olderPart } from "#lib/release-versions.ts";

  interface Props {
    /** Whether someone is signed in: only then is the server asked. */
    signedIn: boolean;
    /** Whether this is the phone app. */
    app: boolean;
  }

  let { signedIn, app }: Props = $props();

  const appVersion = $derived(bridge().appVersion.replace(/^app-/, ""));
  let server = $state<string | null>(null);
  const older = $derived(app && server ? olderPart(appVersion, server) : null);

  $effect(() => {
    if (!signedIn) {
      server = null;
      return;
    }
    let current = true;
    void serverVersion().then((version) => {
      if (current) server = version;
    });
    return () => {
      current = false;
    };
  });
</script>

{#if app || server}
  <div class="versions">
    <!-- Which release this phone and the server run, to compare with the latest on GitHub. -->
    {#if app}<p class="muted">RollCall app {appVersion}</p>{/if}
    {#if server}<p class="muted">RollCall server {server}</p>{/if}
    {#if older === "server"}
      <p class="note">The server is on an older release than this app. Update the server.</p>
    {:else if older === "app"}
      <p class="note">This app is on an older release than the server. Update the app.</p>
    {/if}
  </div>
{/if}

<style>
  .versions {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-width: 560px;
  }

  .versions p {
    margin: 0;
    font-size: 13px;
  }

  .versions .note {
    font-size: 14px;
  }
</style>
