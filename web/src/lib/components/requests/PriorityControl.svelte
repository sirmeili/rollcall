<script lang="ts">
  /** Editors and Admins change a request's priority; nothing else about it. */
  import type { Priority } from "#lib/api/requests.ts";
  import { PRIORITIES, PRIORITY_LABELS } from "#lib/requests/labels.ts";
  import "#lib/requests/requests.css";

  interface Props {
    priority: Priority;
    /** Saves the new priority; rejects with a sentence to show. */
    onchange: (priority: Priority) => Promise<void>;
  }

  let { priority, onchange }: Props = $props();

  // Picked here, until saved; starts at the request's priority.
  let picked = $state<Priority | null>(null);
  const choice = $derived(picked ?? priority);
  let busy = $state(false);
  let message = $state("");

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const from = priority;
    busy = true;
    message = "";
    try {
      await onchange(choice);
      message = `Changed from ${PRIORITY_LABELS[from]} to ${PRIORITY_LABELS[choice]}.`;
      picked = null;
    } catch (error) {
      message = error instanceof Error ? error.message : String(error);
    } finally {
      busy = false;
    }
  }
</script>

<form class="prictl" onsubmit={save}>
  <fieldset>
    <legend>Priority</legend>
    <div class="seg">
      {#each PRIORITIES as value (value)}
        <label>
          <input
            type="radio"
            name="priority"
            {value}
            checked={choice === value}
            onchange={() => (picked = value)}
          /><span>{PRIORITY_LABELS[value]}</span>
        </label>
      {/each}
    </div>
  </fieldset>
  <div class="prirow">
    <button type="submit" disabled={busy || choice === priority}>Change priority</button>
    <span class="muted" role="status">{message}</span>
  </div>
</form>

<style>
  .prictl {
    display: flex;
    flex-direction: column;
    gap: 10px;
    border-top: 1px solid var(--line);
    padding-top: 16px;
  }

  fieldset {
    border: 0;
    margin: 0;
    padding: 0;
    min-width: 0;
  }

  legend {
    padding: 0;
    margin: 0 0 8px;
    font-weight: 600;
    font-size: 14px;
  }

  .prirow {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .prirow .muted {
    font-size: 13px;
  }
</style>
