<script lang="ts">
  /** The Catalog color dialog (docs/mockups/web/Products.html): a product's link and how it
   * was made, a search to pick a catalog color, Clear for a manual link, and Find in store.
   * Save stages the change into the Products page's pending edits; Cancel, Escape or the
   * dimmed page drop it. */
  import type { Product } from "#lib/api/types.ts";
  import { type CatalogEntry, changeFor, clearHint, type LinkPick } from "#lib/catalog-links.ts";
  import { storeSearchUrl } from "#lib/catalog.ts";
  import FindInStore from "#lib/components/catalog/FindInStore.svelte";
  import CatalogColorSearch from "#lib/components/products/CatalogColorSearch.svelte";
  import CurrentLink from "#lib/components/products/CurrentLink.svelte";
  import Ring from "#lib/components/ui/Ring.svelte";
  import { hexText } from "#lib/format.ts";
  import { backCloses } from "#lib/phone/back-layer.svelte.ts";

  interface Props {
    product: Product;
    /** A change already staged for it. */
    staged: LinkPick;
    /** The catalog, once read. */
    entries: CatalogEntry[] | null;
    storeAddress: string | null;
    /** Why the catalog could not be read. */
    failure: string | null;
    /** Who is signed in. */
    me: string;
    onsave: (change: LinkPick) => void;
    onclose: () => void;
  }

  let { product, staged, entries, storeAddress, failure, me, onsave, onclose }: Props = $props();

  // The phone's Back closes it too, as Escape does.
  backCloses(() => onclose());

  // svelte-ignore state_referenced_locally
  let pick = $state<LinkPick>(staged);
  const link = $derived(product.catalog_link);
  const change = $derived(changeFor(link, pick));
  const entry = $derived(
    typeof change === "string" ? entries?.find((e) => e.color.uuid === change) : undefined,
  );
  const manual = $derived(change === undefined ? link?.how === "hand" : typeof change === "string");
  const selected = $derived(
    typeof change === "string"
      ? change
      : change === undefined && link?.in_catalog
        ? link.uuid
        : null,
  );
  const store = $derived.by(() => {
    if (!storeAddress) return null;
    if (entry) {
      return storeSearchUrl(storeAddress, entry.line, entry.color.name, entry.color.bambu_code);
    }
    if (change === undefined && link?.in_catalog && link.line && link.name) {
      return storeSearchUrl(storeAddress, link.line, link.name, link.bambu_code);
    }
    return null;
  });

  let box: HTMLDivElement;

  $effect(() => {
    box.querySelector<HTMLElement>("input, button")?.focus();
  });

  /** Escape cancels; Tab stays inside the dialog. */
  function keydown(event: KeyboardEvent): void {
    if (event.key === "Escape") {
      event.preventDefault();
      onclose();
      return;
    }
    if (event.key !== "Tab") return;
    const all = [...box.querySelectorAll<HTMLElement>("button:not(:disabled), input, a[href]")];
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

<button type="button" class="dim" aria-label="Cancel" tabindex="-1" onclick={onclose}></button>
<div
  class="ccdlg"
  role="dialog"
  aria-modal="true"
  aria-labelledby="cc-title"
  aria-describedby="cc-sub"
  tabindex="-1"
  bind:this={box}
  onkeydown={keydown}
>
  <div class="top">
    <h2 id="cc-title">Catalog color</h2>
    <p class="sub" id="cc-sub">
      <Ring rgba={product.color_rgba} size="sm" />
      {product.display_name} · {product.filament_type} ·
      <span class="mono">#{hexText(product.color_rgba)}</span>
    </p>
  </div>
  <div class="body">
    <div class="sect">
      <CurrentLink {link} {change} {entry} {me} />
      <div class="curactions">
        <button
          type="button"
          disabled={!manual}
          aria-describedby="cc-clear-hint"
          onclick={() => (pick = null)}>Clear</button
        >
        <span class="hint" id="cc-clear-hint">{clearHint(link?.tag_link_exists ?? false)}</span>
        {#if store}<FindInStore href={store} />{/if}
      </div>
    </div>
    <div class="sect">
      {#if failure}
        <p role="alert" class="error">{failure}</p>
      {:else if !entries}
        <p class="muted">Loading the catalog…</p>
      {:else}
        <CatalogColorSearch
          {entries}
          material={product.filament_type}
          {selected}
          onpick={(uuid) => (pick = uuid)}
        />
      {/if}
    </div>
  </div>
  <div class="foot">
    <button type="button" onclick={onclose}>Cancel</button>
    <button
      type="button"
      class="primary"
      disabled={change === staged}
      onclick={() => onsave(change)}>Save</button
    >
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

  .ccdlg {
    position: fixed;
    z-index: 41;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    flex-direction: column;
    width: min(560px, calc(100vw - 32px));
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

  .sub {
    margin: 4px 0 0;
    font-size: 14px;
    color: var(--muted);
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .mono {
    font-family: var(--font-mono);
  }

  .body {
    padding: 16px 22px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .sect {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .curactions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
  }

  .hint {
    font-size: 13px;
    color: var(--muted);
    flex: 1 1 200px;
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
