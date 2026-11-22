<script lang="ts">
  /** A short choice's product on the shopping list: On the shopping list, Partly ordered
   * (n of m spools ordered) or Ordered, linked to its item there. Nothing shows once the
   * item is gone. */
  import type { ShoppingStage } from "#lib/api/requests.ts";

  interface Props {
    shopping: ShoppingStage | null;
  }

  let { shopping }: Props = $props();

  function stageText(shopping: ShoppingStage): string {
    if (shopping.stage === "on_list") return "On the shopping list";
    if (shopping.stage === "ordered") return "Ordered";
    // Partly ordered needs at least 2: one on order, and more to buy.
    return `Partly ordered (${shopping.on_order} of ${shopping.need} spools ordered)`;
  }
</script>

{#if shopping}
  <a class="stage" href={`/shopping-list#shopping-item-${shopping.product_id}`}
    >{stageText(shopping)}</a
  >
{/if}

<style>
  .stage {
    align-self: flex-start;
    margin-top: 4px;
    font-size: 13px;
  }
</style>
