<script lang="ts">
  /** On an item back on the list since it was dismissed: how many spools more it needs than
   * when it was. */
  import type { ShoppingListItem } from "#lib/api/shopping.ts";
  import { spoolsText } from "#lib/shopping-list.ts";

  let { item }: { item: ShoppingListItem } = $props();
</script>

{#if item.new_since_dismissal}
  <span class="new">{spoolsText(item.new_since_dismissal)} more than when dismissed</span>
{/if}

<style>
  .new {
    align-self: flex-start;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--chip);
    font-size: 12px;
    font-weight: 600;
  }
</style>
