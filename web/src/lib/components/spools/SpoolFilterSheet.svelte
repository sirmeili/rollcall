<script lang="ts">
  // The Spools page's filter sheet on a phone (docs/mockups/mobile-web/PhoneSpools.html):
  // State and Type, as the desktop chips and dropdown. Changes apply on "Show N spools";
  // Escape, the dimmed page or Close leave the filters as they were.
  import { keepTabInside } from "#lib/focus-trap.ts";
  import { noFilter, type SpoolFilter, STATE_FILTERS } from "#lib/spools.ts";

  interface Props {
    filter: SpoolFilter;
    /** "All", then each filament type. */
    types: string[];
    /** How many spools a filter matches, from the server. */
    count: (filter: SpoolFilter, signal: AbortSignal) => Promise<number>;
    onapply: (filter: SpoolFilter) => void;
    onclose: () => void;
  }

  let { filter, types, count, onapply, onclose }: Props = $props();

  // The sheet edits a copy; the page's filters change only on Show.
  // svelte-ignore state_referenced_locally
  let draft = $state<SpoolFilter>({ ...filter });
  let matching = $state<number | null>(null);

  let sheet: HTMLDivElement;

  $effect(() => {
    sheet.querySelector<HTMLElement>("button")?.focus();
  });

  // Count the spools the draft matches; a newer draft cancels the older count.
  $effect(() => {
    const asked = { ...draft };
    const controller = new AbortController();
    count(asked, controller.signal).then(
      (n) => {
        if (!controller.signal.aborted) matching = n;
      },
      () => {
        if (!controller.signal.aborted) matching = null;
      },
    );
    return () => controller.abort();
  });

  /** Escape closes; Tab stays inside the sheet. */
  function keydown(event: KeyboardEvent): void {
    if (event.key === "Escape") {
      event.preventDefault();
      onclose();
      return;
    }
    keepTabInside(sheet, event);
  }
</script>

<button type="button" class="dim" aria-label="Close the filters" tabindex="-1" onclick={onclose}
></button>
<div
  class="sheet"
  role="dialog"
  aria-modal="true"
  aria-labelledby="spool-filter-h"
  tabindex="-1"
  bind:this={sheet}
  onkeydown={keydown}
>
  <span class="grip" aria-hidden="true"></span>
  <div class="head">
    <h2 id="spool-filter-h">Filter</h2>
    <button type="button" class="small" onclick={onclose}>Close</button>
  </div>

  <section aria-labelledby="spool-state-h">
    <h3 id="spool-state-h" class="label">State</h3>
    <div class="chips" role="group" aria-labelledby="spool-state-h">
      {#each STATE_FILTERS as option (option.value)}
        <button
          type="button"
          class="chip"
          aria-pressed={draft.state === option.value}
          onclick={() => (draft.state = option.value)}>{option.label}</button
        >
      {/each}
    </div>
  </section>

  <section aria-labelledby="spool-type-h">
    <h3 id="spool-type-h" class="label">Type</h3>
    <div class="chips" role="group" aria-labelledby="spool-type-h">
      {#each types as option (option)}
        <button
          type="button"
          class="chip"
          aria-pressed={draft.type === option}
          onclick={() => (draft.type = option)}>{option}</button
        >
      {/each}
    </div>
  </section>

  <div class="foot">
    <button type="button" onclick={() => (draft = noFilter())}>Clear</button>
    <button type="button" class="primary" onclick={() => onapply(draft)}>
      {#if matching === null}
        Show spools
      {:else}
        Show {matching}
        {matching === 1 ? "spool" : "spools"}
      {/if}
    </button>
  </div>
</div>

<style>
  .dim {
    position: fixed;
    inset: 0;
    z-index: 50;
    border: 0;
    border-radius: 0;
    padding: 0;
    min-height: 0;
    background: rgba(0, 0, 0, 0.45);
  }

  /* Only shown on a phone, so it always rises from the bottom. */
  .sheet {
    position: fixed;
    z-index: 51;
    left: 0;
    right: 0;
    bottom: 0;
    max-height: calc(100dvh - 48px);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 18px;
    padding: 10px 16px calc(18px + env(safe-area-inset-bottom, 0px));
    border-radius: 24px 24px 0 0;
    background: var(--surface);
    box-sizing: border-box;
    outline: none;
  }

  .grip {
    align-self: center;
    width: 40px;
    height: 5px;
    border-radius: 999px;
    background: var(--line);
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  h2,
  h3 {
    margin: 0;
  }

  h2 {
    font-size: 20px;
  }

  section {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .foot {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 10px;
  }
</style>
