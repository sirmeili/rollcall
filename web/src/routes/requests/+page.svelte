<script lang="ts">
  import { describeError } from "#lib/api/errors.ts";
  import {
    listRequests,
    type RequestRow,
    type RequestStatus,
    type RequestTab,
  } from "#lib/api/requests.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import RequestCards from "#lib/components/requests/RequestCards.svelte";
  import RequestTable from "#lib/components/requests/RequestTable.svelte";
  import { canSubmit, seesEveryRequest } from "#lib/requests/access.ts";
  import { STATUS_LABELS } from "#lib/requests/labels.ts";
  import {
    emptyState,
    OPEN_STATUSES,
    SORT_TEXT,
    STAFF_INTRO,
    TABS,
    toggleStatus,
  } from "#lib/requests/list.ts";
  import { viewport } from "#lib/viewport.svelte.ts";

  const screen = viewport();
  const seesAll = $derived(seesEveryRequest(session.user));
  const canNew = $derived(canSubmit(session.user));
  // Editors and Admins who are also Requesters have requests of their own among everyone's.
  const offerMine = $derived(seesAll && canNew);

  let tab = $state<RequestTab>("active");
  let statuses = $state<RequestStatus[]>([]);
  let mine = $state(false);

  let requests = $state<RequestRow[] | null>(null);
  let failure = $state<string | null>(null);

  // Reload whenever the tab or a filter changes. The status filter is for the Active tab.
  $effect(() => {
    const query = {
      tab,
      statuses: seesAll && tab === "active" ? [...statuses] : [],
      mine: offerMine && mine,
    };
    const controller = new AbortController();
    listRequests(query, controller.signal).then(
      (rows) => {
        requests = rows;
        failure = null;
      },
      (error) => {
        if (!controller.signal.aborted) failure = describeError(error);
      },
    );
    return () => controller.abort();
  });

  function show(next: RequestTab): void {
    tab = next;
    requests = null;
  }

  const intro = $derived(
    seesAll
      ? STAFF_INTRO[tab]
      : canNew
        ? "Your print requests. You can edit a request while it's still Submitted."
        : "Your earlier print requests. You can no longer submit or edit requests, but you can still open them and download their files.",
  );
  const empty = $derived(
    emptyState({
      tab,
      seesAll,
      canSubmit: canNew,
      filtered: (tab === "active" && statuses.length > 0) || (offerMine && mine),
    }),
  );
</script>

<svelte:head><title>Requests · RollCall</title></svelte:head>

{#snippet newButton()}
  <a class="button primary" href="/requests/new">
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.4"
      aria-hidden="true"><path d="M12 5v14M5 12h14"></path></svg
    >New request
  </a>
{/snippet}

<div class="page">
  <div class="pagehead">
    <div>
      <h1>Requests</h1>
      <p>{intro}</p>
    </div>
    <!-- On a phone, New request is the bottom bar's centre button instead. -->
    {#if canNew && !screen.phone}{@render newButton()}{/if}
  </div>

  <div class="toolbar">
    <div class="toolbar chips" role="group" aria-label="Show">
      {#each TABS as option (option.value)}
        <button
          type="button"
          class="chip"
          aria-pressed={tab === option.value}
          onclick={() => show(option.value)}>{option.label}</button
        >
      {/each}
    </div>
    {#if seesAll && tab === "active"}
      <div class="toolbar chips" role="group" aria-label="Filter by status">
        {#each OPEN_STATUSES as status (status)}
          <button
            type="button"
            class="chip"
            aria-pressed={statuses.includes(status)}
            onclick={() => (statuses = toggleStatus(statuses, status))}
            >{STATUS_LABELS[status]}</button
          >
        {/each}
      </div>
    {/if}
    {#if offerMine}
      <button type="button" class="chip" aria-pressed={mine} onclick={() => (mine = !mine)}
        >Only mine</button
      >
    {/if}
  </div>

  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if !requests}
    <p class="muted">Loading…</p>
  {:else if requests.length === 0}
    <section class="card empty">
      <h2>{empty.heading}</h2>
      <p class="muted">{empty.text}</p>
      {#if empty.offerNew}{@render newButton()}{/if}
    </section>
  {:else}
    <p class="meta muted">
      <strong>{requests.length}</strong>
      {requests.length === 1 ? "request" : "requests"} · {SORT_TEXT[tab]}
    </p>
    {#if screen.phone}
      <RequestCards {requests} showRequester={seesAll} />
    {:else}
      <RequestTable {requests} showRequester={seesAll} />
    {/if}
  {/if}
</div>

<style>
  .chips {
    gap: 8px;
  }

  .meta {
    margin: -8px 0 0;
    font-size: 14px;
  }

  .meta strong {
    color: var(--text);
  }

  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    text-align: center;
    padding: 56px 24px;
  }

  .empty h2 {
    margin: 0;
  }

  .empty p {
    margin: 0;
    max-width: 460px;
  }
</style>
