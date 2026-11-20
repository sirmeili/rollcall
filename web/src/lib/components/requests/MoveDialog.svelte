<script lang="ts">
  /** Confirms a move to another status, with an optional note or a required reason, as the
   * other dialogs do (the Catalog color dialog's frame), and "Add photos" for a move that
   * takes them (Done). Approve and Reprint ask for the grams of each filament choice, with its
   * product's available grams beside it; Reprint fills in the last attempt's grams. Cancel,
   * Escape or the dimmed page close it without moving. */
  import { untrack } from "svelte";
  import type { Choice, Move, RequestStatus } from "#lib/api/requests.ts";
  import PhotoInput from "#lib/components/requests/PhotoInput.svelte";
  import { keepTabInside } from "#lib/focus-trap.ts";
  import { isReprint, moveWords, NOTE_MAX } from "#lib/requests/labels.ts";
  import { MAX_PHOTOS, pickPhotos } from "#lib/requests/photos.ts";

  interface Props {
    /** The status the request is in now. */
    status: RequestStatus;
    move: Move;
    /** The caller asked for the request. */
    mine: boolean;
    busy: boolean;
    /** The server's problem with the note. */
    problem: string | null;
    /** Why the move failed otherwise. */
    failure: string | null;
    /** Why a photo was refused. */
    photoProblem?: string | null;
    /** The request's filament choices, which Approve and Reprint ask grams for. */
    choices?: Choice[];
    /** The server's problems with the grams, by `grams.<choice ID>`. */
    gramsProblems?: Record<string, string>;
    onconfirm: (note: string, photos: File[], grams?: Record<number, number>) => void;
    onclose: () => void;
  }

  let {
    status,
    move,
    mine,
    busy,
    problem,
    failure,
    photoProblem = null,
    choices = [],
    gramsProblems = {},
    onconfirm,
    onclose,
  }: Props = $props();

  const words = $derived(moveWords(move.to_status, status));
  const label = $derived(move.reason_required ? "Reason" : "Note (optional)");
  const dismiss = $derived(words.dismiss ?? "Cancel");
  const hint = $derived(
    move.reason_required
      ? "The requester sees the reason."
      : mine
        ? "Editors and Admins see the note."
        : "The requester sees the note.",
  );
  let note = $state("");
  let photos = $state<File[]>([]);
  let picked = $state<string | null>(null);
  const photoSaid = $derived(picked ?? photoProblem);

  function pick(chosen: File[]): void {
    const found = pickPhotos(chosen, photos.length);
    photos = [...photos, ...found.files];
    picked = found.problem;
  }

  function unpick(index: number): void {
    photos = photos.filter((_, i) => i !== index);
    picked = null;
  }
  const reprint = $derived(isReprint(status, move.to_status));
  const asksGrams = $derived(move.to_status === "approved" || reprint);
  let grams = $state<Record<number, number | null>>(
    untrack(() =>
      reprint ? Object.fromEntries(choices.map((choice) => [choice.id, choice.grams])) : {},
    ),
  );
  const noGrams = $derived(asksGrams && choices.some((choice) => grams[choice.id] == null));
  const blank = $derived((move.reason_required && !note.trim()) || noGrams);

  let box: HTMLDivElement;

  $effect(() => {
    box.querySelector<HTMLElement>("input, textarea")?.focus();
  });

  /** Escape cancels; Tab stays inside the dialog. */
  function keydown(event: KeyboardEvent): void {
    if (event.key === "Escape") {
      event.preventDefault();
      onclose();
      return;
    }
    keepTabInside(box, event);
  }

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    if (!asksGrams) {
      onconfirm(note, photos);
      return;
    }
    onconfirm(note, photos, Object.fromEntries(choices.map((c) => [c.id, grams[c.id] ?? 0])));
  }
</script>

<button type="button" class="dim" aria-label={dismiss} tabindex="-1" onclick={onclose}></button>
<div
  class="movedlg"
  role="dialog"
  aria-modal="true"
  aria-labelledby="move-title"
  tabindex="-1"
  bind:this={box}
  onkeydown={keydown}
>
  <form onsubmit={submit}>
    <div class="top">
      <h2 id="move-title">{words.question}</h2>
    </div>
    <div class="body">
      {#if asksGrams}
        <fieldset class="grams">
          <legend>Grams for the whole quantity</legend>
          {#each choices as choice (choice.id)}
            {@const problem = gramsProblems[`grams.${choice.id}`]}
            <div class="gram">
              <label for="grams-{choice.id}">{choice.name}</label>
              <span class="gramrow">
                <input
                  id="grams-{choice.id}"
                  type="number"
                  min="1"
                  max="100000"
                  step="1"
                  required
                  aria-describedby="avail-{choice.id}"
                  aria-invalid={problem ? "true" : undefined}
                  bind:value={grams[choice.id]}
                />
                <span class="hint" id="avail-{choice.id}"
                  >about {choice.available_g} g available</span
                >
              </span>
              {#if problem}<p class="error">{problem}</p>{/if}
            </div>
          {/each}
        </fieldset>
      {/if}
      <label for="move-note">{label}</label>
      <textarea
        id="move-note"
        rows="4"
        maxlength={NOTE_MAX}
        required={move.reason_required}
        aria-describedby="move-hint move-count"
        aria-invalid={problem ? "true" : undefined}
        bind:value={note}></textarea>
      <div class="hintrow">
        <span class="hint" id="move-hint">{hint}</span>
        <span class="hint mono" id="move-count">{note.length}/{NOTE_MAX}</span>
      </div>
      {#if problem}<p class="error">{problem}</p>{/if}
      {#if move.photos}
        <div class="photos">
          {#if photos.length}
            <ul>
              {#each photos as photo, i (i)}
                <li>
                  <span class="pname">{photo.name}</span>
                  <button type="button" aria-label="Remove {photo.name}" onclick={() => unpick(i)}
                    >Remove</button
                  >
                </li>
              {/each}
            </ul>
          {/if}
          <PhotoInput disabled={busy || photos.length >= MAX_PHOTOS} onpick={pick} />
          <span class="hint">Up to {MAX_PHOTOS} JPEG or PNG photos, 20 MB each.</span>
          {#if photoSaid}<p class="error">{photoSaid}</p>{/if}
        </div>
      {/if}
      {#if failure}<p role="alert" class="error">{failure}</p>{/if}
    </div>
    <div class="foot">
      <button type="button" onclick={onclose}>{dismiss}</button>
      <button type="submit" class="primary" disabled={busy || blank}>{words.action}</button>
    </div>
  </form>
</div>

<style>
  .dim {
    position: fixed;
    inset: 0;
    z-index: 40;
    border: 0;
    border-radius: 0;
    background: rgba(28, 27, 25, 0.45);
  }

  .movedlg {
    position: fixed;
    z-index: 41;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: min(480px, calc(100vw - 32px));
    max-height: calc(100vh - 64px);
    overflow: auto;
    border: 1px solid var(--line);
    border-radius: 16px;
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  }

  .top {
    padding: 20px 22px 14px;
    border-bottom: 1px solid var(--line);
  }

  h2 {
    margin: 0;
    font-family: var(--font-head);
    font-size: 22px;
  }

  .body {
    padding: 16px 22px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  label {
    font-weight: 600;
  }

  textarea {
    width: 100%;
    box-sizing: border-box;
    resize: vertical;
  }

  .hintrow {
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }

  .hint {
    font-size: 13px;
    color: var(--muted);
  }

  .mono {
    font-family: var(--font-mono);
  }

  .error {
    margin: 0;
  }

  .grams {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin: 0 0 8px;
    padding: 0;
    border: 0;
  }

  legend {
    padding: 0;
    margin-bottom: 6px;
    font-weight: 600;
  }

  .gram {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .gram label {
    font-weight: 400;
  }

  .gramrow {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }

  .gramrow input {
    width: 120px;
  }

  .photos {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 8px;
  }

  .photos ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .photos li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .pname {
    overflow-wrap: anywhere;
    font-size: 14px;
  }

  .foot {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding: 14px 22px 18px;
    border-top: 1px solid var(--line);
  }
</style>
