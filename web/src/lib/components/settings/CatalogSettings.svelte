<script lang="ts">
  /** The Catalog card: the sync status and Refresh now. */
  import { getSyncStatus, refreshCatalog, type SyncStatus } from "#lib/api/catalog.ts";
  import { describeError } from "#lib/api/errors.ts";
  import { attemptNote, failureText, refreshText, versionText } from "#lib/catalog-sync.ts";
  import { dateTime } from "#lib/format.ts";

  let status = $state<SyncStatus | null>(null);
  let failure = $state<string | null>(null);
  let message = $state<string | null>(null);
  let busy = $state(false);

  const warning = $derived(status ? failureText(status) : null);

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
    message = "Checking for a new version…";
    const before = status;
    try {
      status = await refreshCatalog();
      message = refreshText(before, status);
    } catch (error) {
      message = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<section class="card" aria-labelledby="catalog-h">
  <div>
    <h2 id="catalog-h" class="label">Catalog</h2>
    <p class="muted intro">
      A local copy of the Open Filament Database's Bambu Lab colors, for the Catalog page.
    </p>
  </div>

  <div class="status" aria-labelledby="catalog-status-h">
    <h3 id="catalog-status-h" class="label">Status</h3>
    {#if failure}
      <p role="alert" class="error">{failure}</p>
    {:else if !status}
      <p class="muted">Loading…</p>
    {:else}
      {#if warning}
        <div class="fail" role="alert">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.4"
            aria-hidden="true"
            ><path
              d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"
            ></path></svg
          >
          <span>{warning}</span>
        </div>
      {/if}
      <dl>
        <div>
          <dt>Last successful sync</dt>
          <dd class="mono">
            {status.last_success_at ? dateTime(status.last_success_at) : "Never"}
          </dd>
        </div>
        <div>
          <dt>Last attempt</dt>
          <dd>
            <span class="mono"
              >{status.last_attempt_at ? dateTime(status.last_attempt_at) : "Never"}</span
            >
            {#if status.last_result}<span class="note">{attemptNote(status)}</span>{/if}
          </dd>
        </div>
        <div>
          <dt>Dataset version</dt>
          <dd class="mono">{versionText(status.dataset_version)}</dd>
        </div>
      </dl>
    {/if}
    <div class="buttons">
      <button type="button" disabled={busy} onclick={refresh}>Refresh now</button>
      {#if message}<span class="muted" role="status">{message}</span>{/if}
    </div>
  </div>

  <p class="attrib muted">
    Catalog data from the Open Filament Database, used under the MIT license.
  </p>
</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 760px;
  }

  .intro {
    margin: 6px 0 0;
    font-size: 14px;
  }

  .status {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  h3 {
    margin: 0;
  }

  dl {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px 20px;
    margin: 0;
  }

  dt {
    font-size: 12px;
    color: var(--muted);
    font-weight: 600;
  }

  dd {
    margin: 3px 0 0;
    font-size: 14px;
    font-weight: 600;
  }

  .mono {
    font-family: var(--font-mono);
  }

  .note {
    display: block;
    font-weight: 500;
    color: var(--muted);
    font-size: 13px;
  }

  .fail {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--lowbg);
    color: var(--lowtext);
    font-size: 14px;
    font-weight: 600;
    line-height: 1.45;
  }

  .fail svg {
    flex: none;
    margin-top: 2px;
  }

  .buttons {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }

  .attrib {
    margin: 0;
    font-size: 13px;
  }
</style>
