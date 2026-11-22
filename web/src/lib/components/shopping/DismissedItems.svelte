<script lang="ts">
  /** The Dismissed filter of the shopping list: each dismissed item still hidden, with the
   * need it was dismissed at, its reasons and, for Editors and Admins, Bring back. */
  import type { ShoppingListItem } from "#lib/api/shopping.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import Ring from "#lib/components/ui/Ring.svelte";
  import { reasonText, spoolsText } from "#lib/shopping-list.ts";

  interface Props {
    items: ShoppingListItem[];
    /** Bring back a product's item, by the product's ID. */
    onbringback: (productId: number) => void;
  }

  let { items, onbringback }: Props = $props();

  const editor = $derived(session.can("editor"));
</script>

<section class="dismissed" aria-label="Dismissed">
  {#if items.length === 0}
    <p class="muted empty">Nothing is dismissed.</p>
  {:else}
    <ul class="rows">
      {#each items as item (item.product.id)}
        <li class="item">
          <Ring rgba={item.product.color_rgba} size="sm" />
          <div class="body">
            <span class="name">{item.product.display_name}</span>
            <span class="at">Dismissed at {spoolsText(item.dismissed_need ?? 0)} needed</span>
            <ul class="reasons">
              {#each item.reasons as reason, i (i)}
                <li>{reasonText(reason)}</li>
              {/each}
            </ul>
          </div>
          {#if editor}
            <button
              type="button"
              class="small"
              aria-label={`Bring back ${item.product.display_name}`}
              onclick={() => onbringback(item.product.id)}>Bring back</button
            >
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .dismissed {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 16px;
    overflow: hidden;
  }

  .empty {
    margin: 0;
    padding: 16px 18px;
  }

  .rows {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .rows > li + li {
    border-top: 1px solid var(--line);
  }

  .item {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: start;
    gap: 12px;
    padding: 14px 18px;
  }

  .body {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }

  .name {
    font-family: var(--font-head);
    font-weight: 600;
    font-size: 16px;
    overflow-wrap: anywhere;
  }

  .at,
  .reasons {
    font-size: 13px;
    color: var(--muted);
  }

  .reasons {
    margin: 0;
    padding: 0;
    list-style: none;
    overflow-wrap: anywhere;
  }
</style>
