<script lang="ts">
  // Spools on a phone (docs/mockups/mobile-web/PhoneSpools.html): one compact row per spool
  // that expands in place, one at a time. The checkbox is its own tap target, so ticking a
  // spool doesn't expand it.
  import type { SpoolRow } from "#lib/api/types.ts";
  import PctBar from "#lib/components/ui/PctBar.svelte";
  import Ring from "#lib/components/ui/Ring.svelte";
  import StateChip from "#lib/components/ui/StateChip.svelte";
  import { shortDate } from "#lib/format.ts";
  import { nearlyOut, whereText } from "#lib/spools.ts";

  interface Props {
    spools: SpoolRow[];
    /** Spool IDs ticked for a bulk move; null hides the checkboxes (Viewers). */
    selected: Set<number> | null;
    ontoggle?: (id: number) => void;
  }

  let { spools, selected, ontoggle }: Props = $props();

  let expanded = $state<number | null>(null);
</script>

{#if spools.length === 0}
  <p class="list none muted">No spools match.</p>
{:else}
  <ul class="list" class:viewer={!selected}>
    {#each spools as spool (spool.id)}
      {@const open = expanded === spool.id}
      {@const where = whereText(spool)}
      {@const low = nearlyOut(spool)}
      <li class:open class:sel={selected?.has(spool.id)}>
        <div class="srow">
          {#if selected}
            <label class="pick">
              <input
                type="checkbox"
                aria-label="Select spool {spool.id}"
                checked={selected.has(spool.id)}
                onchange={() => ontoggle?.(spool.id)}
              />
            </label>
          {/if}
          <button
            type="button"
            class="crow"
            aria-expanded={open}
            aria-controls="spool-detail-{spool.id}"
            onclick={() => (expanded = open ? null : spool.id)}
          >
            <Ring rgba={spool.product.color_rgba} size="sm" />
            <span class="text">
              <span class="name">{spool.product.display_name}</span>
              <span class="meta mono"
                >{[`#${spool.id}`, spool.placeholder && "no tag yet", where ?? "—"]
                  .filter(Boolean)
                  .join(" · ")}</span
              >
              {#if spool.state === "open"}
                {#if spool.remaining_pct === null}
                  <span class="mini unknown">Not seen by the AMS</span>
                {:else}
                  <span class="mini" class:low>
                    <span class="track" aria-hidden="true">
                      <span style:width="{Math.max(0, Math.min(100, spool.remaining_pct))}%"></span>
                    </span>
                    <span class="pct mono">{spool.remaining_pct}%</span>
                  </span>
                {/if}
              {/if}
            </span>
            <StateChip state={spool.state} />
            <svg
              class="chev"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.4"
              aria-hidden="true"
            >
              <path d="M6 9l6 6 6-6"></path>
            </svg>
          </button>
        </div>
        {#if open}
          <div class="detail" id="spool-detail-{spool.id}">
            <dl>
              <dt>Location</dt>
              <dd>{where ?? "—"}</dd>
              <dt>Left</dt>
              <dd>
                {#if spool.state === "open"}
                  <PctBar pct={spool.remaining_pct} {low} />
                {:else}
                  <span class="muted">—</span>
                {/if}
              </dd>
              <dt>Received</dt>
              <dd class="date">{shortDate(spool.received_at)}</dd>
              <dt>Opened</dt>
              <dd class="date">{shortDate(spool.opened_at)}</dd>
              <dt>Used up</dt>
              <dd class="date">{shortDate(spool.emptied_at)}</dd>
            </dl>
            <a class="button" href="/spools/{spool.id}">View spool</a>
          </div>
        {/if}
      </li>
    {/each}
  </ul>
{/if}

<style>
  .list {
    margin: 0;
    padding: 0;
    list-style: none;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 14px;
    overflow: hidden;
  }

  .none {
    padding: 18px 14px;
  }

  li + li {
    border-top: 1px solid var(--line);
  }

  li.open {
    background: var(--bg);
  }

  li.sel {
    background: var(--chip);
  }

  .srow {
    display: flex;
    align-items: stretch;
  }

  .pick {
    flex: none;
    width: 46px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding-left: 4px;
    cursor: pointer;
  }

  .crow {
    flex: 1;
    min-width: 0;
    display: grid;
    grid-template-columns: 30px minmax(0, 1fr) auto 16px;
    align-items: center;
    justify-content: stretch;
    gap: 10px;
    min-height: 64px;
    padding: 10px 12px 10px 4px;
    border: 0;
    border-radius: 0;
    background: transparent;
    text-align: left;
    font-weight: 400;
  }

  .viewer .crow {
    padding-left: 14px;
  }

  .text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .name {
    font-family: var(--font-head);
    font-weight: 600;
    font-size: 15px;
    line-height: 1.25;
  }

  .meta {
    font-size: 12px;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .mini {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 3px;
  }

  .mini .track {
    flex: 1;
    max-width: 120px;
    height: 4px;
    border-radius: 999px;
    background: var(--track);
    overflow: hidden;
  }

  .mini .track > span {
    display: block;
    height: 100%;
    border-radius: 999px;
    background: var(--fill);
  }

  .mini.low .track > span {
    background: var(--fillLow);
  }

  .mini .pct {
    font-size: 12px;
    font-weight: 700;
  }

  .mini.low .pct {
    color: var(--lowtext);
  }

  .mini.unknown {
    font-size: 12px;
    color: var(--muted);
  }

  .chev {
    color: var(--muted);
    transition: transform 0.15s;
  }

  li.open .chev {
    transform: rotate(180deg);
  }

  .detail {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 2px 14px 14px 90px;
  }

  .viewer .detail {
    padding-left: 54px;
  }

  dl {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 6px 14px;
    margin: 0;
    font-size: 14px;
    align-items: center;
  }

  dt {
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  dd {
    margin: 0;
    display: flex;
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .date {
    font-family: var(--font-mono);
    font-size: 13px;
  }

  .detail .button {
    width: 100%;
    box-sizing: border-box;
  }
</style>
