<script lang="ts">
  /** A shopping list item's reasons, with Remove on each hand-added one for Editors and
   * Admins, Find in store when its product has a Bambu code, Dismiss for Editors and Admins,
   * and its recent history. */
  import type { ShoppingListItem } from "#lib/api/shopping.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import FindInStore from "#lib/components/catalog/FindInStore.svelte";
  import ItemHistory from "#lib/components/shopping/ItemHistory.svelte";
  import { findInStore, reasonText } from "#lib/shopping-list.ts";

  interface Props {
    item: ShoppingListItem;
    storeAddress: string;
    /** Remove a hand-added reason, by its ID. */
    onremove: (id: number) => void;
    /** Dismiss the item, by its product's ID. */
    ondismiss: (productId: number) => void;
  }

  let { item, storeAddress, onremove, ondismiss }: Props = $props();

  const store = $derived(findInStore(storeAddress, item.product));
  const editor = $derived(session.can("editor"));
</script>

<ul class="reasons">
  {#each item.reasons as reason, i (i)}
    {@const text = reasonText(reason)}
    <li>
      <span>{text}</span>
      {#if reason.kind === "hand" && editor}
        <button
          type="button"
          class="small"
          aria-label={`Remove ${text}`}
          onclick={() => onremove(reason.id)}>Remove</button
        >
      {/if}
    </li>
  {/each}
</ul>
{#if store}
  <FindInStore href={store} />
{/if}
{#if editor}
  <button type="button" class="small dismiss" onclick={() => ondismiss(item.product.id)}
    >Dismiss</button
  >
{/if}
<ItemHistory history={item.history} />

<style>
  .reasons {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 14px;
    color: var(--muted);
    overflow-wrap: anywhere;
  }

  .dismiss {
    align-self: flex-start;
  }

  .reasons li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 10px;
  }
</style>
