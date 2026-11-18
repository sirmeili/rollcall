<script lang="ts">
  /** The new-request and edit form (docs/mockups/web/RequestForm.html). Every problem is
   * listed together above the form when it is sent, and each field shows its own. */
  import { tick } from "svelte";
  import { describeError } from "#lib/api/errors.ts";
  import { problemsOf } from "#lib/api/requests.ts";
  import ModelFileField from "#lib/components/requests/ModelFileField.svelte";
  import FilamentField from "#lib/components/requests/FilamentField.svelte";
  import StatusChip from "#lib/components/requests/StatusChip.svelte";
  import { calendarDay } from "#lib/format.ts";
  import {
    LINK_MAX,
    NOTES_MAX,
    TITLE_MAX,
    formProblems,
    summaryHeading,
    type FormField,
    type FormProblem,
    type RequestForm,
  } from "#lib/requests/form.ts";
  import { PRIORITIES, PRIORITY_LABELS } from "#lib/requests/labels.ts";
  import type { PickerOptions } from "#lib/requests/picker.ts";
  import "#lib/requests/requests.css";

  interface Props {
    initial: RequestForm;
    /** The request being edited; null for a new one. */
    editing?: { id: number; neededBy: string } | null;
    options: PickerOptions;
    /** Why the filament picker has nothing to offer. */
    optionsFailure?: string | null;
    /** Sends the form; an API error comes back to show. */
    onsave: (form: RequestForm) => Promise<void>;
  }

  let { initial, editing = null, options, optionsFailure = null, onsave }: Props = $props();

  // A copy to edit; the page passes the starting values once.
  // svelte-ignore state_referenced_locally
  let form = $state<RequestForm>($state.snapshot(initial) as RequestForm);
  let checked = $state(false);
  let busy = $state(false);
  let failure = $state<string | null>(null);
  let fromServer = $state<FormProblem[]>([]);
  let summary = $state<HTMLElement>();

  const today = calendarDay(new Date());
  const local = $derived(checked ? formProblems(form, today, editing?.neededBy ?? "") : []);
  const problems = $derived([
    ...local,
    ...fromServer.filter((p) => !local.some((l) => l.field === p.field)),
  ]);
  const byField = $derived(
    Object.fromEntries(problems.map((p) => [p.field, p.message])) as Partial<
      Record<FormField, string>
    >,
  );
  const hasModel = $derived(
    form.file.status === "kept" || form.file.status === "uploaded" || !!form.link.trim(),
  );

  const TARGETS: Record<string, string> = {
    title: "req-title",
    quantity: "req-quantity",
    priority: "req-title",
    needed_by: "req-needed-by",
    file: "req-file",
    link: "req-link",
    notes: "req-notes",
    choices: "req-filament",
  };

  function jump(event: MouseEvent, field: string): void {
    event.preventDefault();
    document.getElementById(TARGETS[field] ?? "req-title")?.focus();
  }

  function step(by: number): void {
    const now = Number(form.quantity);
    const next = Number.isInteger(now) ? now + by : 1;
    form.quantity = String(Math.min(100, Math.max(1, next)));
  }

  async function send(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    checked = true;
    fromServer = [];
    failure = null;
    if (formProblems(form, today, editing?.neededBy ?? "").length) {
      await tick();
      summary?.focus();
      return;
    }
    busy = true;
    try {
      await onsave(form);
    } catch (error) {
      const refused = problemsOf(error);
      if (refused) {
        fromServer = Object.entries(refused).map(([field, message]) => ({
          field: field as FormField,
          message,
        }));
        await tick();
        summary?.focus();
      } else {
        failure = describeError(error);
      }
    } finally {
      busy = false;
    }
  }
</script>

<form class="formwrap" novalidate onsubmit={send}>
  <a class="req-back" href={editing ? `/requests/${editing.id}` : "/requests"}>
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.2"
      aria-hidden="true"><path d="m15 18-6-6 6-6"></path></svg
    >
    {editing ? `Request #${editing.id}` : "Requests"}
  </a>
  <div class="titlerow">
    {#if editing}
      <h1>Edit request</h1>
      <span class="reqid">#{editing.id}</span>
      <StatusChip status="submitted" />
    {:else}
      <h1>New request</h1>
    {/if}
  </div>

  {#if problems.length}
    <div class="errsum" tabindex="-1" role="alert" bind:this={summary}>
      <h2>{summaryHeading(problems.length, !!editing)}</h2>
      <ul>
        {#each problems as problem (problem.field)}
          <li>
            <a
              href="#{TARGETS[problem.field] ?? 'req-title'}"
              onclick={(e) => jump(e, problem.field)}>{problem.message}</a
            >
          </li>
        {/each}
      </ul>
    </div>
  {/if}

  <section class="card sect" aria-labelledby="req-s1">
    <h2 id="req-s1">What to print</h2>
    <div class="field">
      <label for="req-title">Title</label>
      <input
        id="req-title"
        type="text"
        maxlength={TITLE_MAX}
        autocomplete="off"
        aria-invalid={!!byField.title}
        bind:value={form.title}
      />
      {#if byField.title}<p class="ferr">{byField.title}</p>{/if}
      <span class="counter">{form.title.length} / {TITLE_MAX}</span>
    </div>
    <div class="row3">
      <div class="field">
        <label for="req-quantity">Quantity</label>
        <div class="qty">
          <button type="button" aria-label="One fewer" onclick={() => step(-1)}>−</button>
          <input
            id="req-quantity"
            type="text"
            inputmode="numeric"
            aria-invalid={!!byField.quantity}
            bind:value={form.quantity}
          />
          <button type="button" aria-label="One more" onclick={() => step(1)}>+</button>
        </div>
        {#if byField.quantity}<p class="ferr">{byField.quantity}</p>{/if}
      </div>
      <fieldset class="prifield">
        <legend>Priority</legend>
        <div class="seg">
          {#each PRIORITIES as value (value)}
            <label>
              <input type="radio" name="priority" {value} bind:group={form.priority} /><span
                >{PRIORITY_LABELS[value]}</span
              >
            </label>
          {/each}
        </div>
      </fieldset>
      <div class="field">
        <label for="req-needed-by">Needed by <span class="opt">(optional)</span></label>
        <input
          id="req-needed-by"
          type="date"
          min={today}
          aria-invalid={!!byField.needed_by}
          bind:value={form.neededBy}
        />
        {#if byField.needed_by}<p class="ferr">{byField.needed_by}</p>{/if}
      </div>
    </div>
  </section>

  <section class="card sect" aria-labelledby="req-s2">
    <h2 id="req-s2">The model</h2>
    <p class="lead">Upload the file, link to where it's posted, or both.</p>
    <ModelFileField bind:file={form.file} problem={byField.file ?? null} />
    <div class="field">
      <label for="req-link">Link <span class="opt">(optional)</span></label>
      <input
        id="req-link"
        type="url"
        inputmode="url"
        maxlength={LINK_MAX}
        placeholder="https://makerworld.com/…"
        autocomplete="off"
        aria-describedby="req-link-help"
        aria-invalid={!!byField.link}
        bind:value={form.link}
      />
      <p class="help" id="req-link-help">
        Any http or https address, such as MakerWorld or Printables.
      </p>
      {#if byField.link}<p class="ferr">{byField.link}</p>{/if}
    </div>
    {#if !hasModel}
      <p class="modelrule">No file or link? Then say in the notes where the model is.</p>
    {/if}
  </section>

  <section class="card sect" aria-labelledby="req-s3">
    <h2 id="req-s3">Filament</h2>
    <p class="lead">
      Pick one or more, in the order you'd like them. Add a note to say what each is for.
    </p>
    <FilamentField
      bind:choices={form.choices}
      {options}
      problem={byField.choices ?? null}
      failure={optionsFailure}
    />
  </section>

  <section class="card sect" aria-labelledby="req-s4">
    <h2 id="req-s4">Notes</h2>
    <div class="field">
      <label for="req-notes">
        Notes
        {#if hasModel}<span class="opt">(optional)</span>{:else}<span class="req"
            >(required: say where the model is)</span
          >{/if}
      </label>
      <textarea
        id="req-notes"
        maxlength={NOTES_MAX}
        aria-describedby="req-notes-help"
        aria-invalid={!!byField.notes}
        bind:value={form.notes}></textarea>
      <p class="help" id="req-notes-help">
        Size, infill, supports, anything the printer should know.
      </p>
      {#if byField.notes}<p class="ferr">{byField.notes}</p>{/if}
      <span class="counter">{form.notes.length.toLocaleString("en-US")} / 2,000</span>
    </div>
  </section>

  {#if failure}<p role="alert" class="error">{failure}</p>{/if}

  <div class="formfoot">
    <a class="button" href={editing ? `/requests/${editing.id}` : "/requests"}>Cancel</a>
    <button type="submit" class="primary" disabled={busy}>
      {editing ? "Save changes" : "Submit request"}
    </button>
  </div>
</form>

<style>
  .formwrap {
    max-width: 860px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .titlerow {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 14px;
  }

  .titlerow h1 {
    margin: 0;
  }

  .errsum {
    border: 2px solid var(--danger);
    border-radius: 14px;
    padding: 16px 20px;
    background: var(--surface);
  }

  .errsum h2 {
    margin: 0 0 8px;
    font-family: var(--font-head);
    font-size: 18px;
    color: var(--danger);
  }

  .errsum ul {
    margin: 0;
    padding-left: 20px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .errsum a {
    color: var(--text);
    text-decoration: underline;
    font-weight: 500;
  }

  .row3 {
    display: grid;
    grid-template-columns: 180px 1fr 200px;
    gap: 18px;
    align-items: start;
  }

  .qty {
    display: flex;
    align-items: stretch;
  }

  .qty button {
    width: 44px;
    padding: 0;
    border-radius: 0;
  }

  .qty button:first-child {
    border-radius: 10px 0 0 10px;
  }

  .qty button:last-child {
    border-radius: 0 10px 10px 0;
  }

  .qty input {
    width: 64px;
    text-align: center;
    border-radius: 0;
    border-left: 0;
    border-right: 0;
    font-family: var(--font-mono);
  }

  .prifield {
    border: 0;
    padding: 0;
    margin: 0;
    min-width: 0;
  }

  .prifield legend {
    padding: 0;
    margin: 0 0 6px;
    font-weight: 600;
    font-size: 14px;
  }

  .modelrule {
    margin: 0;
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--chip);
    font-size: 13px;
  }

  textarea {
    min-height: 120px;
  }

  .formfoot {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 10px;
  }

  @media (max-width: 760px) {
    .row3 {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 600px) {
    .formfoot > * {
      flex: 1 1 0;
    }
  }
</style>
