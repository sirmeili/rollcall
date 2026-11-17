<script lang="ts">
  /** A product's Catalog color cell: its linked color and how it was linked, "Not linked",
   * or a warning for a color the catalog has dropped. A change staged in the Catalog color
   * dialog shows as "Not saved yet". Editors press it to open the dialog. */
  import type { CatalogLink } from "#lib/api/types.ts";
  import { type CatalogEntry, cellLabel, linkName, type LinkPick } from "#lib/catalog-links.ts";
  import { howText } from "#lib/catalog.ts";
  import Ring from "#lib/components/ui/Ring.svelte";

  interface Props {
    productName: string;
    link: CatalogLink | null;
    /** A change staged in the dialog, and the color it picks. */
    staged: LinkPick;
    stagedEntry: CatalogEntry | undefined;
    /** Opens the dialog; absent for Viewers. */
    onopen?: (opener: HTMLElement) => void;
  }

  let { productName, link, staged, stagedEntry, onopen }: Props = $props();
</script>

{#snippet inner()}
  {#if staged !== undefined}
    {#if stagedEntry}<Ring rgba="{stagedEntry.color.hexes[0]}FF" size="sm" />{/if}
    <span class="t">
      <span class="n"
        >{stagedEntry
          ? linkName(stagedEntry.line, stagedEntry.color.name)
          : link?.tag_link_exists
            ? "From its tag"
            : "Not linked"}</span
      >
      <span class="pending">Not saved yet</span>
    </span>
  {:else if !link}
    <span class="t"><span class="notlinked">Not linked</span></span>
  {:else if !link.in_catalog}
    <span class="t"
      ><span class="gone"
        ><svg
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.6"
          aria-hidden="true"
          ><path
            d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"
          ></path></svg
        >No longer in the catalog</span
      ></span
    >
  {:else}
    {#if link.hexes}<Ring rgba="{link.hexes[0]}FF" size="sm" />{/if}
    <span class="t">
      <span class="n">{linkName(link.line, link.name)}</span>
      <span class="h">{howText(link.how)}</span>
    </span>
  {/if}
{/snippet}

{#if onopen}
  <button
    type="button"
    class="cc"
    aria-haspopup="dialog"
    aria-label={cellLabel(productName, link)}
    onclick={(event) => onopen(event.currentTarget)}
  >
    {@render inner()}
    <svg
      class="pen"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.2"
      aria-hidden="true"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"></path></svg
    >
  </button>
{:else}
  <div class="cc">{@render inner()}</div>
{/if}

<style>
  .cc {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 44px;
    text-align: left;
    width: 100%;
  }

  button.cc {
    justify-content: flex-start;
    font-weight: 400;
    background: transparent;
    border-color: transparent;
    padding: 4px 8px;
    margin: 0 -8px;
    width: calc(100% + 16px);
  }

  .t {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
    flex: 1;
  }

  .n {
    font-weight: 600;
    white-space: nowrap;
  }

  .h {
    font-size: 12px;
    color: var(--muted);
  }

  .pen {
    color: var(--muted);
    flex: none;
  }

  .notlinked {
    color: var(--muted);
  }

  .gone {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--lowbg);
    color: var(--lowtext);
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 12px;
    font-weight: 700;
    white-space: nowrap;
  }

  .pending {
    font-size: 12px;
    font-weight: 700;
    align-self: flex-start;
    background: var(--chip);
    border-radius: 6px;
    padding: 1px 8px;
  }
</style>
