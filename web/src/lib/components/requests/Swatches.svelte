<script lang="ts">
  /** A request's filament as rings, the first few then "+N". The names are for screen
   * readers. */
  import type { Swatch } from "#lib/api/requests.ts";
  import HexRing from "#lib/components/catalog/HexRing.svelte";

  let { choices, most = 4 }: { choices: Swatch[]; most?: number } = $props();
</script>

<span class="fils">
  {#each choices.slice(0, most) as choice, i (i)}
    <HexRing hexes={choice.hexes} />
  {/each}
  {#if choices.length > most}<span class="more" aria-hidden="true">+{choices.length - most}</span
    >{/if}
  <span class="sr-only">Filament: {choices.map((c) => c.name).join(", ")}</span>
</span>

<style>
  .fils {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }

  .fils :global(.ring) {
    width: 22px;
    height: 22px;
    border-width: 6px;
  }

  .fils :global(.ring.multi::after) {
    inset: 6px;
  }

  .more {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--muted);
  }
</style>
