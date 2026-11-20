<script lang="ts">
  import { page } from "$app/state";
  import { ApiError } from "#lib/api/client.ts";
  import { describeError } from "#lib/api/errors.ts";
  import {
    changePriority,
    fileUrl,
    getRequest,
    type Move,
    moveRequest,
    type Priority,
    type PrintRequest,
    problemsOf,
  } from "#lib/api/requests.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import ChoiceList from "#lib/components/requests/ChoiceList.svelte";
  import MoveButtons from "#lib/components/requests/MoveButtons.svelte";
  import MoveDialog from "#lib/components/requests/MoveDialog.svelte";
  import RequestPhotos from "#lib/components/requests/RequestPhotos.svelte";
  import PriorityChip from "#lib/components/requests/PriorityChip.svelte";
  import PriorityControl from "#lib/components/requests/PriorityControl.svelte";
  import RequestHistory from "#lib/components/requests/RequestHistory.svelte";
  import StatusChip from "#lib/components/requests/StatusChip.svelte";
  import { calendarDay, shortDate } from "#lib/format.ts";
  import { whyNoEdit } from "#lib/requests/access.ts";
  import { neededByDate, relativeDay, relativeTime, sizeText } from "#lib/requests/labels.ts";
  import { uploadPhotos } from "#lib/requests/photos.ts";
  import "#lib/requests/requests.css";

  const id = $derived(Number(page.params.id));

  let request = $state<PrintRequest | null>(null);
  let failure = $state<string | null>(null);

  // The move being confirmed, and how it went.
  let moving = $state<Move | null>(null);
  let busy = $state(false);
  let moveProblem = $state<string | null>(null);
  let moveFailure = $state<string | null>(null);
  let photoProblem = $state<string | null>(null);
  // Said when someone else moved the request first.
  let changed = $state<string | null>(null);

  function load(): void {
    getRequest(id).then(
      (found) => (request = found),
      (error) => (failure = describeError(error)),
    );
  }

  $effect(() => {
    request = null;
    failure = null;
    changed = null;
    if (!Number.isInteger(id) || id <= 0) {
      failure = "Not found. It may have been removed.";
      return;
    }
    load();
  });

  function pick(move: Move): void {
    moving = move;
    moveProblem = null;
    moveFailure = null;
    photoProblem = null;
  }

  /** Upload the photos chosen in the dialog; their upload IDs, or null if one was refused. */
  async function uploaded(photos: File[]): Promise<string[] | null> {
    try {
      return await uploadPhotos(photos);
    } catch (error) {
      photoProblem = (error as Error).message;
      return null;
    }
  }

  async function confirmMove(
    shown: PrintRequest,
    move: Move,
    note: string,
    photos: File[],
  ): Promise<void> {
    busy = true;
    moveProblem = null;
    moveFailure = null;
    photoProblem = null;
    try {
      const photoIds = await uploaded(photos);
      if (photoIds === null) return;
      request = await moveRequest(id, shown.status, move.to_status, note, photoIds);
      moving = null;
      changed = null;
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        // Someone else moved it first: say so, and show it as it is now.
        moving = null;
        changed = describeError(error);
        load();
      } else {
        const problems = problemsOf(error);
        if (problems?.note) moveProblem = problems.note;
        else if (problems?.photos) photoProblem = problems.photos;
        else moveFailure = describeError(error);
      }
    } finally {
      busy = false;
    }
  }

  async function setPriority(priority: Priority): Promise<void> {
    try {
      request = await changePriority(id, priority);
    } catch (error) {
      throw new Error(describeError(error), { cause: error });
    }
  }

  const today = calendarDay(new Date());
</script>

<svelte:head><title>{request ? request.title : "Request"} · RollCall</title></svelte:head>

<div class="req-page">
  <a class="req-back" href="/requests">
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.2"
      aria-hidden="true"><path d="m15 18-6-6 6-6"></path></svg
    >
    Requests
  </a>

  {#if changed}<p role="alert" class="error">{changed}</p>{/if}

  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if !request}
    <p class="muted">Loading…</p>
  {:else}
    <div class="head">
      <div>
        <h1>{request.title}</h1>
        <div class="chips">
          <span class="reqid">#{request.id}</span>
          <StatusChip status={request.status} />
          <PriorityChip priority={request.priority} />
        </div>
        {#if request.attempt >= 2}
          <p class="attempt">Attempt {request.attempt}</p>
        {/if}
        <p class="byline">
          Requested by {request.requester.username} · submitted {relativeTime(request.created_at)}
        </p>
        {#if session.user?.id === request.requester.id && !request.can_edit}
          <p class="noedit">{whyNoEdit(session.user, request)}</p>
        {/if}
      </div>
      <div class="acts">
        <MoveButtons status={request.status} moves={request.moves} {busy} onpick={pick} />
        {#if request.can_edit}
          <a class="button" href="/requests/{request.id}/edit">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.2"
              aria-hidden="true"
              ><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"></path></svg
            >Edit
          </a>
        {/if}
      </div>
    </div>

    {#if moving}
      {@const shown = request}
      {@const move = moving}
      <MoveDialog
        status={shown.status}
        {move}
        mine={session.user?.id === request.requester.id}
        {busy}
        problem={moveProblem}
        failure={moveFailure}
        {photoProblem}
        onconfirm={(note, photos) => confirmMove(shown, move, note, photos)}
        onclose={() => (moving = null)}
      />
    {/if}

    <div class="grid">
      <div class="col">
        <section class="card sect" aria-labelledby="h-model">
          <h2 id="h-model">The model</h2>
          {#if request.file}
            <div class="filecard" class:failed={request.file.missing}>
              <span class="fi" aria-hidden="true">
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  ><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><path
                    d="M14 3v6h6"
                  ></path></svg
                >
              </span>
              <span class="meta">
                <span class="fname">{request.file.name}</span>
                <span class="fsize">
                  {request.file.kind.toUpperCase()} · {sizeText(request.file.size)}
                </span>
              </span>
              <span class="acts">
                {#if request.file.missing}
                  <span class="missing">File missing</span>
                {:else}
                  <a
                    class="button"
                    href={fileUrl(request.id)}
                    download={request.file.name}
                    aria-label="Download {request.file.name}">Download</a
                  >
                {/if}
              </span>
            </div>
          {/if}
          {#if request.link}
            <div class="filecard linkcard">
              <span class="fi" aria-hidden="true">
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  ><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"></path><path
                    d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"
                  ></path></svg
                >
              </span>
              <span class="meta">
                <span class="fname">Link</span>
                <span class="fsize">{request.link}</span>
              </span>
              <span class="acts">
                <a class="button" href={request.link} target="_blank" rel="noopener noreferrer"
                  >Open link</a
                >
              </span>
            </div>
          {/if}
          {#if !request.file && !request.link}
            <p class="nomodel">No file or link. The notes say where the model is.</p>
          {/if}
        </section>

        {#if request.photos.length || request.can_change_photos}
          <RequestPhotos {request} onchange={(changed) => (request = changed)} />
        {/if}

        <section class="card sect" aria-labelledby="h-fil">
          <h2 id="h-fil">Filament</h2>
          <ChoiceList choices={request.choices} storeAddress={request.store_address} />
        </section>

        <section class="card sect" aria-labelledby="h-notes">
          <h2 id="h-notes">Notes</h2>
          {#if request.notes}
            <p class="notes">{request.notes}</p>
          {:else}
            <p class="muted nonotes">No notes.</p>
          {/if}
        </section>

        <section class="card sect" aria-labelledby="h-hist">
          <div class="histhead">
            <h2 id="h-hist">History</h2>
            <p class="muted">Newest first.</p>
          </div>
          <RequestHistory history={request.history} />
        </section>
      </div>

      <aside class="col" aria-label="Request details">
        <section class="card sect" aria-labelledby="h-req">
          <h2 id="h-req">Request</h2>
          <dl class="facts">
            <dt>Requester</dt>
            <dd>{request.requester.username}</dd>
            <dt>Quantity</dt>
            <dd class="mono">{request.quantity}</dd>
            <dt>Needed by</dt>
            <dd>
              {#if request.needed_by}
                <span class="mono">{neededByDate(request.needed_by)}</span>
                <span class="rel">{relativeDay(request.needed_by, today)}</span>
              {:else}
                <span class="muted">No date</span>
              {/if}
            </dd>
            <dt>Submitted</dt>
            <dd>
              <span class="mono">{shortDate(request.created_at)}</span>
              <span class="rel">{relativeTime(request.created_at)}</span>
            </dd>
          </dl>
          {#if request.can_change_priority}
            <PriorityControl priority={request.priority} onchange={setPriority} />
          {/if}
        </section>
      </aside>
    </div>
  {/if}
</div>

<style>
  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
  }

  .acts {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  h1 {
    margin: 0;
    overflow-wrap: anywhere;
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin-top: 10px;
  }

  .attempt {
    margin: 6px 0 0;
    font-size: 14px;
    font-weight: 600;
  }

  .byline {
    margin: 8px 0 0;
    color: var(--muted);
    font-size: 14px;
  }

  .noedit {
    margin: 8px 0 0;
    font-size: 14px;
    font-weight: 600;
  }

  .grid {
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    align-items: flex-start;
  }

  .col {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 20px;
    flex: 999 1 560px;
  }

  aside.col {
    flex: 1 1 300px;
  }

  .linkcard .fname {
    font-family: var(--font-body);
    font-weight: 600;
  }

  .missing {
    font-weight: 600;
    color: var(--danger);
  }

  .nomodel {
    margin: 0;
    padding: 12px 14px;
    border-radius: 10px;
    background: var(--chip);
    font-size: 14px;
  }

  .notes {
    margin: 0;
    white-space: pre-wrap;
    line-height: 1.6;
    font-size: 15px;
    max-width: 68ch;
    overflow-wrap: anywhere;
  }

  .nonotes {
    margin: 0;
    font-size: 14px;
  }

  .histhead {
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex-wrap: wrap;
  }

  .histhead p {
    margin: 0;
    font-size: 14px;
  }

  .facts {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 12px 16px;
    margin: 0;
    align-items: baseline;
  }

  .facts dt {
    font-size: 13px;
    color: var(--muted);
  }

  .facts dd {
    margin: 0;
    font-size: 15px;
  }

  .rel {
    display: block;
    font-size: 12px;
    color: var(--muted);
    margin-top: 2px;
  }
</style>
