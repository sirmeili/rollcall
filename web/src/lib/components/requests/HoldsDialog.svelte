<script lang="ts">
  /** The holds editor for one filament choice, in the frame of the other dialogs (MoveDialog):
   * new grams for the choice, which holds them again; each hold's spool and grams, or its
   * removal; and a hold on any Sealed or Open spool, of another product too. Each change is
   * made straight away through `onchange`; Close, Escape or the dimmed page close it, and
   * Tab stays inside it. */
  import { untrack } from "svelte";
  import {
    addHold,
    changeHold,
    type Choice,
    type HoldChange,
    removeHold,
    setChoiceGrams,
  } from "#lib/api/requests.ts";
  import { listSpools } from "#lib/api/stock.ts";
  import type { SpoolRow } from "#lib/api/types.ts";
  import HoldRow from "#lib/components/requests/HoldRow.svelte";
  import { keepTabInside } from "#lib/focus-trap.ts";
  import { spoolText } from "#lib/requests/labels.ts";

  interface Props {
    requestId: number;
    choice: Choice;
    busy: boolean;
    /** Why the last change was refused. */
    failure: string | null;
    onchange: (change: HoldChange) => void;
    onclose: () => void;
  }

  let { requestId, choice, busy, failure, onchange, onclose }: Props = $props();

  let spools = $state<SpoolRow[]>([]);
  let grams = $state<number | null>(untrack(() => choice.grams));
  let addSpool = $state<number | null>(null);
  let addGrams = $state<number | null>(null);
  const holds = $derived(choice.holds ?? []);
  const title = $derived(`Holds for ${choice.name}`);

  $effect(() => {
    listSpools({ states: ["sealed", "open"], limit: 200 }).then(
      (page) => (spools = page.items),
      () => (spools = []),
    );
  });

  let box: HTMLDivElement;

  $effect(() => {
    box.querySelector<HTMLElement>("input")?.focus();
  });

  /** Escape closes; Tab stays inside the dialog. */
  function keydown(event: KeyboardEvent): void {
    if (event.key === "Escape") {
      event.preventDefault();
      onclose();
      return;
    }
    keepTabInside(box, event);
  }

  function holdAgain(event: SubmitEvent): void {
    event.preventDefault();
    const given = Number(grams);
    onchange((from) => setChoiceGrams(requestId, from, choice.id, given));
  }

  function add(event: SubmitEvent): void {
    event.preventDefault();
    const spool = Number(addSpool);
    const given = Number(addGrams);
    onchange((from) => addHold(requestId, from, choice.id, spool, given));
  }
</script>

<button type="button" class="dim" aria-label="Close" tabindex="-1" onclick={onclose}></button>
<div
  class="holdsdlg"
  role="dialog"
  aria-modal="true"
  aria-labelledby="holds-title"
  tabindex="-1"
  bind:this={box}
  onkeydown={keydown}
>
  <div class="top">
    <h2 id="holds-title">{title}</h2>
  </div>
  <div class="body">
    <form class="row" onsubmit={holdAgain}>
      <label for="holds-grams">Grams for the whole quantity</label>
      <span class="line">
        <input id="holds-grams" type="number" min="1" max="100000" step="1" bind:value={grams} />
        <button type="submit" disabled={busy}>Hold again</button>
      </span>
      <span class="hint">Releases its holds and holds these grams again.</span>
    </form>

    <h3>Held</h3>
    {#each holds as hold (`${hold.id}:${hold.spool_id}:${hold.grams}`)}
      <HoldRow
        {hold}
        {spools}
        {busy}
        onsave={(spool, given) =>
          onchange((from) => changeHold(requestId, from, hold.id, spool, given))}
        onremove={() => onchange((from) => removeHold(requestId, from, hold.id))}
      />
    {:else}
      <p class="hint">Nothing held</p>
    {/each}

    <form class="row" onsubmit={add}>
      <h3>Add a hold</h3>
      <span class="line">
        <select aria-label="Spool to hold" bind:value={addSpool}>
          <option value={null}>Choose a spool</option>
          {#each spools as spool (spool.id)}
            <option value={spool.id}>{spoolText(spool)}</option>
          {/each}
        </select>
        <input
          type="number"
          min="1"
          max="100000"
          step="1"
          aria-label="Grams to hold"
          bind:value={addGrams}
        />
      </span>
      <span class="line">
        <button type="submit" disabled={busy || addSpool === null || addGrams == null}
          >Add hold</button
        >
      </span>
    </form>
    {#if failure}<p role="alert" class="error">{failure}</p>{/if}
  </div>
  <div class="foot">
    <button type="button" onclick={onclose}>Close</button>
  </div>
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

  .holdsdlg {
    position: fixed;
    z-index: 41;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: min(520px, calc(100vw - 32px));
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

  h3 {
    margin: 8px 0 0;
    font-size: 15px;
  }

  .body {
    padding: 16px 22px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .row {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin: 0;
    padding: 0;
    border: 0;
  }

  .line {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  label {
    font-weight: 600;
  }

  select {
    flex: 1 1 200px;
    min-width: 0;
  }

  input {
    width: 110px;
  }

  .hint {
    margin: 0;
    font-size: 13px;
    color: var(--muted);
  }

  .error {
    margin: 0;
  }

  .foot {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding: 14px 22px 18px;
    border-top: 1px solid var(--line);
  }
</style>
