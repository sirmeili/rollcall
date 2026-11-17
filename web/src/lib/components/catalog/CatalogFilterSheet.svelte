<script lang="ts">
  // The Catalog page's filter sheet on a phone (docs/mockups/mobile-web/PhoneCatalog.html):
  // materials and what to show. Changes apply on "Show N colors"; Escape, the dimmed page
  // or Close leave the filter as it was.
  import type { FilamentLine } from "#lib/api/catalog.ts";
  import {
    applyFilter,
    type CatalogFilter,
    countColors,
    materialCounts,
    noFilter,
  } from "#lib/catalog.ts";

  interface Props {
    lines: FilamentLine[];
    filter: CatalogFilter;
    onapply: (filter: CatalogFilter) => void;
    onclose: () => void;
  }

  let { lines, filter, onapply, onclose }: Props = $props();

  // The sheet edits a copy; the page's filter changes only on Show.
  // svelte-ignore state_referenced_locally
  let draft = $state<CatalogFilter>({ ...filter, types: [...filter.types] });
  const count = $derived(countColors(applyFilter(lines, draft)));
  const counts = $derived(materialCounts(lines, draft.showDiscontinued));

  let sheet: HTMLDivElement;

  $effect(() => {
    sheet.querySelector<HTMLElement>("button")?.focus();
  });

  function toggleType(type: string): void {
    draft.types = draft.types.includes(type)
      ? draft.types.filter((t) => t !== type)
      : [...draft.types, type];
  }

  /** Escape closes; Tab stays inside the sheet. */
  function keydown(event: KeyboardEvent): void {
    if (event.key === "Escape") {
      event.preventDefault();
      onclose();
      return;
    }
    if (event.key !== "Tab") return;
    const all = [...sheet.querySelectorAll<HTMLElement>("button, input")];
    const first = all[0];
    const last = all[all.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
</script>

<button type="button" class="dim" aria-label="Close the filters" tabindex="-1" onclick={onclose}
></button>
<div
  class="sheet"
  role="dialog"
  aria-modal="true"
  aria-labelledby="catalog-filter-h"
  tabindex="-1"
  bind:this={sheet}
  onkeydown={keydown}
>
  <span class="grip" aria-hidden="true"></span>
  <div class="head">
    <h2 id="catalog-filter-h">Filter</h2>
    <button type="button" class="small" onclick={onclose}>Close</button>
  </div>

  <section aria-labelledby="catalog-type-h">
    <h3 id="catalog-type-h" class="label">Type</h3>
    <div class="chips" role="group" aria-labelledby="catalog-type-h">
      {#each counts as entry (entry.type)}
        <button
          type="button"
          class="chip"
          aria-pressed={draft.types.includes(entry.type)}
          onclick={() => toggleType(entry.type)}
          >{entry.type} <span class="n">{entry.count}</span></button
        >
      {/each}
    </div>
  </section>

  <section aria-labelledby="catalog-show-h">
    <h3 id="catalog-show-h" class="label">Show</h3>
    <label class="check">
      <input type="checkbox" bind:checked={draft.owned} />
      Owned
    </label>
    <label class="check">
      <input type="checkbox" bind:checked={draft.similarOnly} />
      Has similar in stock
    </label>
    <label class="check">
      <input type="checkbox" bind:checked={draft.showDiscontinued} />
      Show discontinued
    </label>
  </section>

  <div class="foot">
    <button type="button" onclick={() => (draft = { ...noFilter(), query: draft.query })}
      >Clear</button
    >
    <button type="button" class="primary" onclick={() => onapply(draft)}>
      Show {count}
      {count === 1 ? "color" : "colors"}
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

  .n {
    margin-left: 4px;
    font-family: var(--font-mono);
    font-size: 12px;
    opacity: 0.75;
  }

  .check {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 44px;
    font-weight: 600;
  }

  .foot {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 10px;
  }
</style>
