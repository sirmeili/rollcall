<script lang="ts">
  /** The Requests list on a phone (docs/mockups/mobile-web/PhoneRequestsList.html). */
  import type { RequestRow } from "#lib/api/requests.ts";
  import ModelSourceText from "#lib/components/requests/ModelSourceText.svelte";
  import PriorityChip from "#lib/components/requests/PriorityChip.svelte";
  import StatusChip from "#lib/components/requests/StatusChip.svelte";
  import Swatches from "#lib/components/requests/Swatches.svelte";
  import { calendarDay } from "#lib/format.ts";
  import { neededByDate, relativeDay, relativeTime } from "#lib/requests/labels.ts";

  interface Props {
    requests: RequestRow[];
    showRequester: boolean;
  }

  let { requests, showRequester }: Props = $props();
  const today = calendarDay(new Date());
</script>

<ul class="rlist">
  {#each requests as request (request.id)}
    <li class="rcard">
      <div class="rtop">
        {#if showRequester}
          <span class="who"
            ><span class="sr-only">Requester:</span> {request.requester.username}</span
          >
        {/if}
        <PriorityChip priority={request.priority} />
        <StatusChip status={request.status} />
        <span class="num">#{request.id}</span>
      </div>
      <h2 class="rtitle"><a href="/requests/{request.id}">{request.title}</a></h2>
      <div class="rsub">
        <span>Qty <span class="mono">{request.quantity}</span></span>
        <ModelSourceText model={request.model} />
        <span>Submitted {relativeTime(request.created_at)}</span>
      </div>
      <div class="rfoot">
        {#if request.needed_by}
          <span
            >Needed by <span class="mono">{neededByDate(request.needed_by)}</span>
            <span class="muted">· {relativeDay(request.needed_by, today)}</span></span
          >
        {:else}
          <span class="muted">No needed-by date</span>
        {/if}
        <Swatches choices={request.choices} />
      </div>
    </li>
  {/each}
</ul>

<style>
  .rlist {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .rcard {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 14px;
    border: 1px solid var(--line);
    border-radius: 14px;
    background: var(--surface);
  }

  .rcard:focus-within {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .rtop {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .who {
    font-weight: 600;
    font-size: 14px;
  }

  .num {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--muted);
  }

  .rtitle {
    margin: 0;
    font-family: var(--font-head);
    font-weight: 600;
    font-size: 17px;
    line-height: 1.3;
  }

  .rtitle a {
    outline: none;
  }

  .rtitle a::after {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: 14px;
  }

  .rsub {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 12px;
    font-size: 13px;
    color: var(--muted);
  }

  .rfoot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding-top: 8px;
    border-top: 1px solid var(--line);
    font-size: 14px;
  }
</style>
