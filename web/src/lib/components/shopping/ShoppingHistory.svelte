<script lang="ts">
  /** A shopping list item's recent shopping list history, newest first: what was done, by
   * whom and when, and its on order after. */
  import type { ShoppingHistoryEntry } from "#lib/api/shopping.ts";
  import { shoppingHistoryText, shoppingHistoryWhen } from "#lib/shopping-list.ts";

  let { entries }: { entries: ShoppingHistoryEntry[] } = $props();
</script>

{#if entries.length > 0}
  <ol class="history" aria-label="Recent history">
    {#each entries as entry, i (i)}
      <li>
        <span class="what">{shoppingHistoryText(entry)}</span>
        <span class="when">{shoppingHistoryWhen(entry)}</span>
      </li>
    {/each}
  </ol>
{/if}

<style>
  .history {
    margin: 0;
    padding: 8px 0 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 4px;
    border-top: 1px dashed var(--line);
    font-size: 13px;
  }

  .history li {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 8px;
  }

  .what {
    font-weight: 600;
  }

  .when {
    color: var(--muted);
    overflow-wrap: anywhere;
  }
</style>
