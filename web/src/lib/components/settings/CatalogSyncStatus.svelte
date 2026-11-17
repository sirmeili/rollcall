<script lang="ts">
  /** The Catalog card's sync status, for each of its two sources, and Refresh now, which
   * syncs both. */
  import { getSyncStatus, refreshCatalog, type SyncStatus } from "#lib/api/catalog.ts";
  import { describeError } from "#lib/api/errors.ts";
  import { refreshText, SOURCES } from "#lib/catalog-sync.ts";
  import SourceSyncStatus from "#lib/components/settings/SourceSyncStatus.svelte";

  let status = $state<SyncStatus | null>(null);
  let failure = $state<string | null>(null);
  let message = $state<string | null>(null);
  let busy = $state(false);

  async function load(): Promise<void> {
    try {
      status = await getSyncStatus();
      failure = null;
    } catch (error) {
      failure = describeError(error);
    }
  }

  $effect(() => {
    void load();
  });

  async function refresh(): Promise<void> {
    busy = true;
    message = "Checking both sources for a new version…";
    try {
      status = await refreshCatalog();
      message = refreshText(status);
    } catch (error) {
      message = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<div class="status" aria-labelledby="catalog-status-h">
  <h3 id="catalog-status-h" class="label">Status</h3>
  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if !status}
    <p class="muted">Loading…</p>
  {:else}
    {#each SOURCES as source (source.key)}
      <SourceSyncStatus
        id="catalog-{source.key}"
        name={source.name}
        host={source.host}
        status={status[source.key]}
        version={source.key === "ofdb"}
      />
    {/each}
  {/if}
  <div class="buttons">
    <button type="button" disabled={busy} onclick={refresh}>Refresh now</button>
    {#if message}<span class="muted" role="status">{message}</span>{/if}
  </div>
</div>

<style>
  .status {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  h3 {
    margin: 0;
  }

  .buttons {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }

  .error {
    margin: 0;
  }
</style>
