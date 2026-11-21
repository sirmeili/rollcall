<script lang="ts">
  import { selectionText } from "#lib/spools.ts";

  interface Props {
    count: number;
    locations: string[];
    busy: boolean;
    /** On a phone: two lines, pinned above the bottom bar (docs/mockups/mobile-web/
     * PhoneSpools.html). */
    pinned?: boolean;
    onmove: (location: string | null) => void;
    onclear: () => void;
  }

  let { count, locations, busy, pinned = false, onmove, onclear }: Props = $props();
  let location = $state("");

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    onmove(location.trim() || null);
  }
</script>

{#snippet moveTo()}
  <label>
    Move to
    <input
      type="text"
      list="known-locations"
      maxlength="100"
      placeholder="Blank clears it"
      bind:value={location}
    />
  </label>
  <datalist id="known-locations">
    {#each locations as known (known)}<option value={known}></option>{/each}
  </datalist>
  <button type="submit" class="primary" disabled={busy}>Move</button>
{/snippet}

{#if pinned}
  <form class="bar pinned" onsubmit={submit} aria-label="Move selected spools">
    <div class="line">
      <strong>{count} selected</strong>
      <button type="button" class="small" onclick={onclear}>Clear</button>
    </div>
    <div class="line">{@render moveTo()}</div>
  </form>
{:else}
  <form class="bar" onsubmit={submit} aria-label="Move selected spools">
    <strong>{selectionText(count)}</strong>
    <span class="grow"></span>
    {@render moveTo()}
    <button type="button" onclick={onclear}>Clear</button>
  </form>
{/if}

<style>
  .bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 12px;
    background: var(--text);
    color: var(--bg);
  }

  strong {
    font-size: 15px;
  }

  .grow {
    flex: 1;
  }

  label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 600;
  }

  input {
    min-width: 180px;
    background: var(--surface);
  }

  /* Pinned above the phone's bottom bar, so it stays in view while the list scrolls. */
  .pinned {
    position: fixed;
    left: 10px;
    right: 10px;
    bottom: calc(var(--bottom-bar, 84px) + 10px);
    z-index: 30;
    flex-direction: column;
    align-items: stretch;
    flex-wrap: nowrap;
    gap: 10px;
    padding: 12px 14px;
    border-radius: 14px;
    box-shadow: 0 6px 22px rgba(0, 0, 0, 0.3);
  }

  .line {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .pinned .small {
    background: transparent;
    color: inherit;
    border-color: var(--muted);
  }

  .pinned label {
    flex: 1;
    min-width: 0;
    white-space: nowrap;
  }

  .pinned input {
    flex: 1;
    min-width: 0;
    color: var(--text);
  }
</style>
