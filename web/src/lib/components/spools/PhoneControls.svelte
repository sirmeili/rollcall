<script lang="ts">
  // The Spools page's search and Filter button on a phone (docs/mockups/mobile-web/
  // PhoneSpools.html). While a filter is on, a chip under the search sums it up.
  import { filterSummary, filtersOn, type SpoolFilter } from "#lib/spools.ts";

  interface Props {
    search: string;
    filter: SpoolFilter;
    onsearch: (search: string) => void;
    /** Opens the filter sheet. */
    onopen: () => void;
    onclear: () => void;
  }

  let { search, filter, onsearch, onopen, onclear }: Props = $props();

  const on = $derived(filtersOn(filter));
</script>

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
        aria-label="Search spools"
        placeholder="Product, type, location or notes"
        maxlength="100"
        value={search}
        oninput={(event) => onsearch(event.currentTarget.value)}
      />
    </label>
    <button
      type="button"
      class="filter"
      class:on={on > 0}
      aria-haspopup="dialog"
      aria-label={on > 0 ? `Filter, ${on} on` : "Filter"}
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
      {#if on > 0}<span class="count" aria-hidden="true">{on}</span>{/if}
    </button>
  </div>

  {#if on > 0}
    <div class="quick" role="group" aria-label="Filters on">
      <span class="sumchip">
        <button type="button" class="label-button" onclick={onopen}>{filterSummary(filter)}</button>
        <button type="button" class="x" aria-label="Clear the filters" onclick={onclear}>✕</button>
      </span>
      <button type="button" class="clear" onclick={onclear}>Clear</button>
    </div>
  {/if}
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
    min-width: 0;
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
    background: var(--surface);
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

  .quick {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .sumchip {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    background: var(--text);
    color: var(--bg);
  }

  .sumchip button {
    min-height: 40px;
    border: 0;
    background: transparent;
    color: inherit;
    font-weight: 600;
  }

  .label-button {
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
  }
</style>
