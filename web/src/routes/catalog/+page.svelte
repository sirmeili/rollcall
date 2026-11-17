<script lang="ts">
  /** The Catalog page: every Bambu Lab color, by filament line, from the local copy of the
   * Open Filament Database, with what is owned and a way to buy it. Search and filters run
   * here over the one catalog read. */
  import { type Catalog, getCatalog } from "#lib/api/catalog.ts";
  import { describeError } from "#lib/api/errors.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import {
    applyFilter,
    type CatalogFilter,
    materials,
    noFilter,
    summaryText,
  } from "#lib/catalog.ts";
  import { versionText } from "#lib/catalog-sync.ts";
  import CatalogControls from "#lib/components/catalog/CatalogControls.svelte";
  import CatalogEmpty from "#lib/components/catalog/CatalogEmpty.svelte";
  import CatalogFilterSheet from "#lib/components/catalog/CatalogFilterSheet.svelte";
  import LineGroup from "#lib/components/catalog/LineGroup.svelte";
  import { shortDate } from "#lib/format.ts";
  import { viewport } from "#lib/viewport.svelte.ts";

  let catalog = $state<Catalog | null>(null);
  let failure = $state<string | null>(null);
  let filter = $state<CatalogFilter>(noFilter());
  let collapsed = $state<Set<string>>(new Set());
  let sheetOpen = $state(false);
  // One catalog color at a time is expanded.
  let expanded = $state<string | null>(null);

  const screen = viewport();
  const lines = $derived(catalog?.lines ?? []);
  const types = $derived(materials(lines));
  const groups = $derived(applyFilter(lines, filter));
  const summary = $derived(summaryText(lines, filter));

  async function load(): Promise<void> {
    failure = null;
    try {
      catalog = await getCatalog();
    } catch (error) {
      failure = describeError(error);
    }
  }

  function toggle(uuid: string): void {
    const next = new Set(collapsed);
    if (!next.delete(uuid)) next.add(uuid);
    collapsed = next;
  }

  function apply(next: CatalogFilter): void {
    filter = next;
    sheetOpen = false;
  }

  $effect(() => {
    void load();
  });
</script>

<svelte:head><title>Catalog · RollCall</title></svelte:head>

<div class="page">
  <div class="pagehead">
    <div>
      <h1>Catalog</h1>
      <p>Every Bambu Lab color, and the spools on hand that look like it.</p>
    </div>
  </div>

  {#if failure}
    <p role="alert" class="error">
      {failure} <button class="small" onclick={load}>Try again</button>
    </p>
  {:else if !catalog}
    <p class="muted">Loading…</p>
  {:else if !catalog.synced}
    <CatalogEmpty admin={session.can("admin")} onsynced={load} />
  {:else}
    <CatalogControls bind:filter {types} phone={screen.phone} onopen={() => (sheetOpen = true)} />
    <p class="summary" aria-live="polite">{summary}</p>
    {#if groups.length === 0}
      <p class="muted">
        No catalog colors match.
        <button type="button" class="small" onclick={() => (filter = noFilter())}
          >Clear filters</button
        >
      </p>
    {:else}
      <div class="groups">
        {#each groups as group (group.line.uuid)}
          <LineGroup
            {group}
            open={!collapsed.has(group.line.uuid)}
            ontoggle={() => toggle(group.line.uuid)}
            cutoff={catalog.cutoff}
            storeAddress={catalog.store_address}
            {expanded}
            onexpand={(uuid) => (expanded = expanded === uuid ? null : uuid)}
          />
        {/each}
      </div>
    {/if}
    <p class="pagefoot">
      Catalog data from the Open Filament Database (MIT license) · Updated {shortDate(
        catalog.last_success_at,
      )}, dataset {versionText(catalog.dataset_version)}
      {#if catalog.out_of_date}
        · <span class="stale">Catalog may be out of date</span>
      {/if}
    </p>
    <p class="pagefoot credit">
      Bambu codes matched to tags using BambuStudio's color code list (AGPL-3.0)
    </p>
  {/if}
</div>

{#if sheetOpen && catalog}
  <CatalogFilterSheet {lines} {filter} onapply={apply} onclose={() => (sheetOpen = false)} />
{/if}

<style>
  .page {
    gap: 20px;
  }

  .summary {
    margin: 0;
    font-size: 14px;
    color: var(--muted);
  }

  .groups {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .pagefoot {
    margin: 8px 0 0;
    font-size: 13px;
    color: var(--muted);
  }

  .credit {
    margin-top: -12px;
  }

  .stale {
    color: var(--lowtext);
    font-weight: 600;
  }
</style>
