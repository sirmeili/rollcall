<script lang="ts">
  /** The Catalog color dialog's link: the saved one and how it was made, or the change
   * picked in the dialog, marked "Not saved yet". */
  import type { CatalogLink } from "#lib/api/types.ts";
  import {
    type CatalogEntry,
    droppedText,
    handText,
    linkName,
    type LinkPick,
  } from "#lib/catalog-links.ts";
  import Ring from "#lib/components/ui/Ring.svelte";

  interface Props {
    /** The saved link. */
    link: CatalogLink | null;
    /** The change picked, if any, and the color it picks. */
    change: LinkPick;
    entry: CatalogEntry | undefined;
    /** Who is signed in, for "Linked by hand by … when you save". */
    me: string;
  }

  let { link, change, entry, me }: Props = $props();
</script>

<p class="label" id="cc-current-l">{change === undefined ? "Current link" : "New link"}</p>
<div class="cur" role="group" aria-labelledby="cc-current-l">
  {#if change !== undefined}
    {#if entry}
      <Ring rgba="{entry.color.hexes[0]}FF" size="sm" />
      <span class="t">
        <span class="n"
          >{linkName(entry.line, entry.color.name)}
          {#if entry.color.bambu_code}<span class="mono">{entry.color.bambu_code}</span>{/if}</span
        >
        <span class="h">Linked by hand by {me} when you save</span>
      </span>
    {:else}
      <span class="t">
        <span class="n" class:quiet={!link?.tag_link_exists}
          >{link?.tag_link_exists ? "From its tag" : "Not linked"}</span
        >
      </span>
    {/if}
    <span class="pending">Not saved yet</span>
  {:else if !link}
    <span class="t"><span class="n quiet">Not linked</span></span>
  {:else if !link.in_catalog}
    <span class="t">
      <span><span class="gone">No longer in the catalog</span></span>
      <span class="h">{droppedText(link)}</span>
    </span>
  {:else}
    {#if link.hexes}<Ring rgba="{link.hexes[0]}FF" size="sm" />{/if}
    <span class="t">
      <span class="n"
        >{linkName(link.line, link.name)}
        {#if link.bambu_code}<span class="mono">{link.bambu_code}</span>{/if}</span
      >
      <span class="h">{link.how === "hand" ? handText(link) : "From its tag"}</span>
    </span>
  {/if}
</div>

<style>
  .label {
    margin: 0;
  }

  .cur {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    border: 1px solid var(--line);
    border-radius: 12px;
    background: var(--bg);
  }

  .t {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex: 1;
    min-width: 0;
  }

  .n {
    font-weight: 600;
  }

  .n.quiet {
    color: var(--muted);
    font-weight: 500;
  }

  .mono {
    font-family: var(--font-mono);
    font-weight: 500;
    color: var(--muted);
  }

  .h {
    font-size: 13px;
    color: var(--muted);
  }

  .gone {
    display: inline-flex;
    background: var(--lowbg);
    color: var(--lowtext);
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 12px;
    font-weight: 700;
  }

  .pending {
    font-size: 12px;
    font-weight: 700;
    background: var(--chip);
    border-radius: 6px;
    padding: 2px 8px;
    white-space: nowrap;
  }
</style>
