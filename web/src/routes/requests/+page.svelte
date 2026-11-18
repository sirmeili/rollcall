<script lang="ts">
  import { describeError } from "#lib/api/errors.ts";
  import { listRequests, type RequestRow } from "#lib/api/requests.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import RequestCards from "#lib/components/requests/RequestCards.svelte";
  import RequestTable from "#lib/components/requests/RequestTable.svelte";
  import { canSubmit, seesEveryRequest } from "#lib/requests/access.ts";
  import { viewport } from "#lib/viewport.svelte.ts";

  const screen = viewport();
  const seesAll = $derived(seesEveryRequest(session.user));
  const canNew = $derived(canSubmit(session.user));

  let requests = $state<RequestRow[] | null>(null);
  let failure = $state<string | null>(null);

  $effect(() => {
    listRequests().then(
      (rows) => (requests = rows),
      (error) => (failure = describeError(error)),
    );
  });

  const intro = $derived(
    seesAll
      ? "Print requests from everyone. Most urgent first."
      : canNew
        ? "Your print requests. You can edit a request while it's still Submitted."
        : "Your earlier print requests. You can no longer submit or edit requests, but you can still open them and download their files.",
  );
  const emptyHeading = $derived(
    seesAll
      ? "No print requests yet"
      : canNew
        ? "You haven't asked for any prints yet"
        : "You don't have any print requests",
  );
  const emptyText = $derived(
    seesAll
      ? canNew
        ? "Requests from everyone with the Requester permission show up here. Start one yourself with New request."
        : "Requests from everyone with the Requester permission show up here."
      : canNew
        ? "Ask for something to be printed: add a model file or link, pick filament, and say when you need it."
        : "You can no longer submit print requests.",
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
    {#if canNew}{@render newButton()}{/if}
  </div>

  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if !requests}
    <p class="muted">Loading…</p>
  {:else if requests.length === 0}
    <section class="card empty">
      <h2>{emptyHeading}</h2>
      <p class="muted">{emptyText}</p>
      {#if canNew}{@render newButton()}{/if}
    </section>
  {:else}
    <p class="meta muted">
      <strong>{requests.length}</strong>
      {requests.length === 1 ? "request" : "requests"} · Most urgent first, then by needed-by date, then
      oldest first
    </p>
    {#if screen.phone}
      <RequestCards {requests} showRequester={seesAll} />
    {:else}
      <RequestTable {requests} showRequester={seesAll} />
    {/if}
  {/if}
</div>

<style>
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
