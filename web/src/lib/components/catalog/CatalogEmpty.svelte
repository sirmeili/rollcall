<script lang="ts">
  /** Before the first sync: Admins can download the catalog here or open its settings;
   * others are told an admin can. */
  import { refreshCatalog } from "#lib/api/catalog.ts";
  import { describeError } from "#lib/api/errors.ts";
  import { refreshText } from "#lib/catalog-sync.ts";

  interface Props {
    admin: boolean;
    /** Called after a sync that downloaded the catalog. */
    onsynced: () => void;
  }

  let { admin, onsynced }: Props = $props();

  let busy = $state(false);
  let message = $state<string | null>(null);

  async function refresh(): Promise<void> {
    busy = true;
    message = "Downloading…";
    try {
      const status = await refreshCatalog();
      if (status.ofdb.last_result === "updated") {
        message = null;
        onsynced();
      } else {
        message = refreshText(status);
      }
    } catch (error) {
      message = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<section class="card empty" aria-labelledby="catalog-empty-h">
  <span class="emptyicon" aria-hidden="true"
    ><svg
      width="28"
      height="28"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"><path d="M12 3v12M7 10l5 5 5-5M5 21h14"></path></svg
    ></span
  >
  <h2 id="catalog-empty-h">The catalog hasn't been downloaded yet.</h2>
  {#if admin}
    <p>Download it now, or set how often it syncs in Settings.</p>
    <div class="btnrow">
      <button type="button" class="primary" disabled={busy} onclick={refresh}>Refresh now</button>
      <a class="button" href="/settings#catalog">Catalog settings</a>
      {#if message}<span class="muted" role="status">{message}</span>{/if}
    </div>
  {:else}
    <p>An admin can download it from Settings.</p>
  {/if}
</section>

<style>
  .empty {
    display: flex;
    flex-direction: column;
    gap: 14px;
    align-items: flex-start;
    max-width: 640px;
    padding: 28px;
  }

  h2 {
    margin: 0;
    font-size: 22px;
  }

  p {
    margin: 0;
    color: var(--muted);
  }

  .emptyicon {
    width: 56px;
    height: 56px;
    border-radius: 14px;
    background: var(--chip);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--muted);
  }

  .btnrow {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
  }
</style>
