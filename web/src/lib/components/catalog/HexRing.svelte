<script lang="ts">
  /** A catalog color's swatch ring: one color as the ring, or equal segments for a
   * multi-color catalog color. Decorative; the name says what it is. */
  interface Props {
    /** RRGGBB, without the #. */
    hexes: string[];
  }

  let { hexes }: Props = $props();

  const segments = $derived.by(() => {
    const step = 100 / hexes.length;
    return hexes
      .map((hex, i) => `#${hex} ${(i * step).toFixed(2)}% ${((i + 1) * step).toFixed(2)}%`)
      .join(", ");
  });
</script>

{#if hexes.length > 1}
  <span
    class="ring multi"
    aria-hidden="true"
    style:background="conic-gradient(from -90deg, {segments})"
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
