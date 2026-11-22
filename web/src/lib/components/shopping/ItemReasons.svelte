<script lang="ts">
  /** A shopping list item's reasons, and Find in store when its product has a Bambu code. */
  import type { ShoppingListItem } from "#lib/api/shopping.ts";
  import FindInStore from "#lib/components/catalog/FindInStore.svelte";
  import { findInStore, reasonText } from "#lib/shopping-list.ts";

  interface Props {
    item: ShoppingListItem;
    storeAddress: string;
  }

  let { item, storeAddress }: Props = $props();

  const store = $derived(findInStore(storeAddress, item.product));
</script>

<ul class="reasons">
  {#each item.reasons as reason, i (i)}
    <li>{reasonText(reason)}</li>
  {/each}
</ul>
{#if store}
  <FindInStore href={store} />
{/if}

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
</style>
