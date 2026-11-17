<script lang="ts">
  /** The Catalog page's search and filters. Wider screens show every filter as a chip; a
   * phone shows a Filter button for the filter sheet and chips for what is on, as
   * Inventory does (docs/mockups/web/Catalog.html, mobile-web/PhoneCatalog.html). */
  import { activeFilters, type CatalogFilter, isFiltered, noFilter } from "#lib/catalog.ts";
  import { chosenTypes, typeSummary } from "#lib/inventory.ts";

  interface Props {
    filter: CatalogFilter;
    /** The materials in the catalog. */
    types: string[];
    phone: boolean;
    /** Opens the filter sheet. */
    onopen: () => void;
  }

  let { filter = $bindable(), types, phone, onopen }: Props = $props();

  const active = $derived(activeFilters(filter, types));
  const typeText = $derived(typeSummary(chosenTypes(filter.types, types), types));

  function toggleType(type: string): void {
    filter.types = filter.types.includes(type)
      ? filter.types.filter((t) => t !== type)
      : [...filter.types, type];
  }
</script>

{#snippet stockChips()}
  <button
    type="button"
    class="chip"
    aria-pressed={filter.owned}
    onclick={() => (filter.owned = !filter.owned)}>Owned</button
  >
  <button
    type="button"
    class="chip"
    aria-pressed={filter.similarOnly}
    onclick={() => (filter.similarOnly = !filter.similarOnly)}>Has similar in stock</button
  >
{/snippet}

<div class="controls">
  <div class="top">
    <label class="search">
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.2"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7"></circle>
        <path d="M20 20l-3.5-3.5"></path>
      </svg>
      <input
        type="search"
        aria-label="Search line or color"
        placeholder="Search line or color"
        autocomplete="off"
        bind:value={filter.query}
      />
    </label>
    {#if phone}
      <button
        type="button"
        class="filter"
        class:on={active > 0}
        aria-haspopup="dialog"
        aria-label={active > 0 ? `Filter, ${active} on` : "Filter"}
        onclick={onopen}
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.2"
          stroke-linecap="round"
          aria-hidden="true"
        >
          <path d="M4 6h16M7 12h10M10 18h4"></path>
        </svg>
        Filter
        {#if active > 0}<span class="count" aria-hidden="true">{active}</span>{/if}
      </button>
    {/if}
  </div>

  <div class="chiprow" role="group" aria-label={phone ? "Quick filters" : "Filters"}>
    {#if phone}
      {@render stockChips()}
      {#if typeText}
        <span class="onchip">
          <button type="button" class="lb" onclick={onopen}>{typeText}</button>
          <button
            type="button"
            class="x"
            aria-label="Clear the types"
            onclick={() => (filter.types = [])}>✕</button
          >
        </span>
      {/if}
      {#if filter.showDiscontinued}
        <span class="onchip">
          <button type="button" class="lb" onclick={onopen}>Discontinued shown</button>
          <button
            type="button"
            class="x"
            aria-label="Hide discontinued colors"
            onclick={() => (filter.showDiscontinued = false)}>✕</button
          >
        </span>
      {/if}
    {:else}
      {#each types as type (type)}
        <button
          type="button"
          class="chip"
          aria-pressed={filter.types.includes(type)}
          onclick={() => toggleType(type)}>{type}</button
        >
      {/each}
      <span class="sep" aria-hidden="true"></span>
      {@render stockChips()}
      <button
        type="button"
        class="chip"
        aria-pressed={filter.showDiscontinued}
        onclick={() => (filter.showDiscontinued = !filter.showDiscontinued)}
        >Show discontinued</button
      >
    {/if}
    {#if isFiltered(filter)}
      <button type="button" class="clear" onclick={() => (filter = noFilter())}>Clear</button>
    {/if}
  </div>
</div>

<style>
  .controls {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .top {
    display: flex;
    gap: 8px;
  }

  .search {
    position: relative;
    flex: 1;
    max-width: 420px;
  }

  .search svg {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--muted);
  }

  .search input {
    width: 100%;
    padding-left: 38px;
    box-sizing: border-box;
  }

  .filter {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .filter.on {
    background: var(--text);
    border-color: var(--text);
    color: var(--bg);
  }

  .count {
    min-width: 20px;
    padding: 0 6px;
    border-radius: 999px;
    background: var(--accent);
    color: var(--onaccent);
    font-size: 12px;
    font-weight: 700;
    text-align: center;
  }

  .chiprow {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .chiprow:empty {
    display: none;
  }

  .sep {
    width: 1px;
    align-self: stretch;
    background: var(--line);
    margin: 4px;
  }

  .onchip {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    background: var(--text);
    color: var(--bg);
  }

  .onchip button {
    min-height: 40px;
    border: 0;
    background: transparent;
    color: inherit;
    font-weight: 600;
  }

  .lb {
    padding: 0 4px 0 14px;
  }

  .x {
    padding: 0 12px 0 6px;
  }

  .clear {
    border: 0;
    background: transparent;
    color: var(--muted);
    text-decoration: underline;
    padding: 0 8px;
  }
</style>
