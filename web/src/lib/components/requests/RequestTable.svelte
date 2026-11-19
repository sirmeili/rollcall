<script lang="ts">
  /** The Requests list on a wide screen (docs/mockups/web/RequestsList.html). */
  import type { RequestRow } from "#lib/api/requests.ts";
  import ModelSourceText from "#lib/components/requests/ModelSourceText.svelte";
  import PriorityChip from "#lib/components/requests/PriorityChip.svelte";
  import StatusChip from "#lib/components/requests/StatusChip.svelte";
  import Swatches from "#lib/components/requests/Swatches.svelte";
  import { calendarDay, shortDate } from "#lib/format.ts";
  import { neededByDate, relativeDay, relativeTime } from "#lib/requests/labels.ts";

  interface Props {
    requests: RequestRow[];
    /** Editors and Admins see who asked. */
    showRequester: boolean;
  }

  let { requests, showRequester }: Props = $props();
  const today = calendarDay(new Date());
</script>

<div class="tablebox">
  <table>
    <thead>
      <tr>
        <th scope="col">Priority</th>
        <th scope="col">Request</th>
        {#if showRequester}<th scope="col">Requester</th>{/if}
        <th scope="col">Needed by</th>
        <th scope="col">Filament</th>
        <th scope="col">Status</th>
        <th scope="col">Submitted</th>
      </tr>
    </thead>
    <tbody>
      {#each requests as request (request.id)}
        <tr>
          <td><PriorityChip priority={request.priority} /></td>
          <td>
            <a class="rtitle" href="/requests/{request.id}">{request.title}</a>
            <span class="rsub">
              <span>Qty <span class="mono">{request.quantity}</span></span>
              <ModelSourceText model={request.model} />
              <span class="mono">#{request.id}</span>
            </span>
          </td>
          {#if showRequester}<td>{request.requester.username}</td>{/if}
          <td>
            {#if request.needed_by}
              <span class="mono">{neededByDate(request.needed_by)}</span>
              <span class="rel">{relativeDay(request.needed_by, today)}</span>
            {:else}
              <span class="muted">No date</span>
            {/if}
          </td>
          <td><Swatches choices={request.choices} /></td>
          <td><StatusChip status={request.status} /></td>
          <td>
            <span class="mono">{shortDate(request.created_at)}</span>
            <span class="rel">{relativeTime(request.created_at)}</span>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .rtitle {
    display: block;
    font-family: var(--font-head);
    font-weight: 600;
    font-size: 16px;
  }

  .rsub {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 12px;
    margin-top: 2px;
    font-size: 13px;
    color: var(--muted);
  }

  .rel {
    display: block;
    font-size: 12px;
    color: var(--muted);
  }
</style>
