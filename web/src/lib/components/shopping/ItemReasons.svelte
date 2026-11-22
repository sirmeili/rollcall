<script lang="ts">
  /** A shopping list item's reasons, each print request linked for people allowed to see it,
   * with Remove on each hand-added one for Editors and Admins; the size it uses, Find in
   * store when its product has a Bambu code, Dismiss for Editors and Admins, and its recent
   * history. */
  import type { ShoppingList, ShoppingListItem } from "#lib/api/shopping.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import FindInStore from "#lib/components/catalog/FindInStore.svelte";
  import ShoppingHistory from "#lib/components/shopping/ShoppingHistory.svelte";
  import ItemSize from "#lib/components/shopping/ItemSize.svelte";
  import { findInStore, reasonText } from "#lib/shopping-list.ts";

  interface Props {
    item: ShoppingListItem;
    storeAddress: string;
    /** Remove a hand-added reason, by its ID. */
    onremove: (id: number) => void;
    /** The list once the item is changed. */
    onchanged: (list: ShoppingList) => void;
    /** Dismiss the item, by its product's ID. */
    ondismiss: (productId: number) => void;
  }

  let { item, storeAddress, onremove, onchanged, ondismiss }: Props = $props();

  const store = $derived(findInStore(storeAddress, item.product));
  const editor = $derived(session.can("editor"));
</script>

<ul class="reasons">
  {#each item.reasons as reason, i (i)}
    {@const text = reasonText(reason)}
    <li>
      {#if reason.kind === "request" && reason.request_id !== null}
        <a href={`/requests/${reason.request_id}`}>{text}</a>
      {:else}
        <span>{text}</span>
      {/if}
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
<ItemSize {item} {onchanged} />
{#if store}
  <FindInStore href={store} />
{/if}
{#if editor}
  <button type="button" class="small dismiss" onclick={() => ondismiss(item.product.id)}
    >Dismiss</button
  >
{/if}
<ShoppingHistory entries={item.shopping_history} />

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
