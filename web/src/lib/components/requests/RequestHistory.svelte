<script lang="ts">
  /** A request's history, newest first: submitted, edited, and priority and status
   * changes, each with its note or reason. */
  import type { HistoryEntry } from "#lib/api/requests.ts";
  import { dateTime } from "#lib/format.ts";
  import { historyDetail, historyTitle, relativeTime } from "#lib/requests/labels.ts";

  let { history }: { history: HistoryEntry[] } = $props();

  const ICONS: Record<HistoryEntry["kind"], string> = {
    submitted: "M12 5v14M5 12h14",
    edited: "M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z",
    priority_changed: "M7 4v16M7 4l10 4-10 4",
    status_changed: "M5 12h14M13 6l6 6-6 6",
  };
</script>

<ol class="history">
  {#each history as entry, i (i)}
    {@const detail = historyDetail(entry)}
    <li>
      <span class="hi" aria-hidden="true">
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.4"><path d={ICONS[entry.kind]}></path></svg
        >
      </span>
      <span>
        <span class="what">{historyTitle(entry)}</span>
        {#if detail}<span class="detail">{detail}</span>{/if}
        {#if entry.note}<span class="detail">{entry.note}</span>{/if}
      </span>
      <span class="when">{dateTime(entry.at)}<span>{relativeTime(entry.at)}</span></span>
    </li>
  {/each}
</ol>

<style>
  .history {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  li {
    display: grid;
    grid-template-columns: 28px minmax(0, 1fr) auto;
    gap: 12px;
    padding: 12px 0;
    align-items: start;
  }

  li + li {
    border-top: 1px solid var(--line);
  }

  .hi {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--chip);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--muted);
  }

  .what {
    font-weight: 600;
  }

  .detail {
    display: block;
    font-size: 13px;
    color: var(--muted);
    margin-top: 2px;
  }

  .when {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--muted);
    white-space: nowrap;
    text-align: right;
  }

  .when span {
    display: block;
    font-family: var(--font-body);
  }
</style>
