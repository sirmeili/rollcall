<script lang="ts">
  /** Add to shopping list on an expanded catalog color (Editors and Admins): a number of
   * spools of it, put on its product's item. A color with no linked product gets a "From the
   * catalog" product on the server. */
  import { describeError } from "#lib/api/errors.ts";
  import { addByHand } from "#lib/api/shopping.ts";
  import { spoolsProblem } from "#lib/shopping-add.ts";
  import { spoolsText } from "#lib/shopping-list.ts";

  interface Props {
    /** The catalog color's UUID and name. */
    uuid: string;
    name: string;
  }

  let { uuid, name }: Props = $props();

  let spools = $state<number | null>(1);
  let saving = $state(false);
  let done = $state<string | null>(null);
  let failure = $state<string | null>(null);

  const problem = $derived(spoolsProblem(spools));

  async function add(): Promise<void> {
    if (problem || spools === null) return;
    saving = true;
    done = failure = null;
    try {
      await addByHand({ catalog_color: uuid }, spools);
      done = `Added ${spoolsText(spools)} of ${name} to the shopping list.`;
    } catch (error) {
      failure = describeError(error);
    } finally {
      saving = false;
    }
  }
</script>

<div class="addlist">
  <input
    type="number"
    min="1"
    max="999"
    step="1"
    aria-label={`Spools of ${name}`}
    bind:value={spools}
  />
  <button type="button" disabled={problem !== null || saving} onclick={add}
    >Add to shopping list</button
  >
  {#if done}<p role="status" class="muted">{done}</p>{/if}
  {#if failure}<p role="alert" class="error">{failure}</p>{/if}
</div>

<style>
  .addlist {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .addlist input {
    width: 80px;
  }

  .addlist p {
    margin: 0;
    flex-basis: 100%;
  }
</style>
