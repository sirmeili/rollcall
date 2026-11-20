<script lang="ts">
  /** The moves the caller may make from here, as the server lists them; the main next step is
   * the primary button. */
  import type { Move } from "#lib/api/requests.ts";
  import { mainMove, moveWords } from "#lib/requests/labels.ts";

  interface Props {
    moves: Move[];
    busy: boolean;
    onpick: (move: Move) => void;
  }

  let { moves, busy, onpick }: Props = $props();

  const main = $derived(mainMove(moves));
</script>

{#if moves.length}
  <div class="moves" role="group" aria-label="Move this request">
    {#each moves as move (move.to_status)}
      <button
        type="button"
        class:primary={move.to_status === main}
        disabled={busy}
        onclick={() => onpick(move)}>{moveWords(move.to_status).action}</button
      >
    {/each}
  </div>
{/if}

<style>
  .moves {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
</style>
