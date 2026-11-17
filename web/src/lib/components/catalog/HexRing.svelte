<script lang="ts">
  /** A catalog color's swatch ring: one color as the ring, or for a multi-color catalog
   * color, its colors around the ring. A gradient blends them, wrapping back to the first;
   * a coextruded one shows them in equal, hard-edged segments, as it prints. Decorative;
   * the name says what it is. */
  interface Props {
    /** RRGGBB, without the #. */
    hexes: string[];
    /** The colors blend along the filament. */
    gradient?: boolean;
  }

  let { hexes, gradient = false }: Props = $props();

  const stops = $derived.by(() => {
    const step = 100 / hexes.length;
    const at = (i: number) => (i * step).toFixed(2);
    if (gradient) {
      return [...hexes, hexes[0]].map((hex, i) => `#${hex} ${at(i)}%`).join(", ");
    }
    return hexes.map((hex, i) => `#${hex} ${at(i)}% ${at(i + 1)}%`).join(", ");
  });
</script>

{#if hexes.length > 1}
  <span
    class="ring multi"
    aria-hidden="true"
    style="background: conic-gradient(from -90deg, {stops})"
  ></span>
{:else}
  <span class="ring" aria-hidden="true" style:border-color="#{hexes[0]}"></span>
{/if}

<style>
  .ring {
    display: inline-block;
    flex: none;
    width: 30px;
    height: 30px;
    border-radius: 50%;
    border: 8px solid;
    background: var(--bg);
    box-sizing: border-box;
    box-shadow: var(--ringShadowSmall);
  }

  .multi {
    position: relative;
    border: 0;
  }

  .multi::after {
    content: "";
    position: absolute;
    inset: 8px;
    border-radius: 50%;
    background: var(--bg);
  }
</style>
