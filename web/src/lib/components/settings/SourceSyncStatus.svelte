<script lang="ts">
  /** One catalog source's sync status: a warning when its last attempt failed, its last
   * successful sync, its last attempt with the result, and (OFDB only) the dataset
   * version. */
  import type { SourceStatus } from "#lib/api/catalog.ts";
  import { attemptNote, failureText, versionText } from "#lib/catalog-sync.ts";
  import { dateTime } from "#lib/format.ts";

  interface Props {
    /** Names the block, such as "Open Filament Database". */
    name: string;
    /** The server it contacts. */
    host: string;
    status: SourceStatus;
    /** Show the dataset version (OFDB's only). */
    version: boolean;
    /** For the heading's id. */
    id: string;
  }

  let { name, host, status, version, id }: Props = $props();

  const warning = $derived(failureText(status));
</script>

<section class="src" aria-labelledby="{id}-h">
  <div class="srchead">
    <h4 id="{id}-h">{name}</h4>
    <span class="srchost">{host}</span>
  </div>
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
    {#if version}
      <div>
        <dt>Dataset version</dt>
        <dd class="mono">{versionText(status.dataset_version)}</dd>
      </div>
    {/if}
  </dl>
</section>

<style>
  .src {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .srchead {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 4px 10px;
  }

  h4 {
    margin: 0;
    font-size: 15px;
  }

  .srchost {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--muted);
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
</style>
