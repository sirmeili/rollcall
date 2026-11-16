<script lang="ts">
  /** The Catalog card's settings: how often the catalog syncs and the similarity cutoff. */
  import { describeError } from "#lib/api/errors.ts";
  import {
    getSettings,
    saveSettings,
    settingProblems,
    type SettingOut,
  } from "#lib/api/settings.ts";
  import { cutoffProblem, cutoffValue, SCHEDULES, scheduleHelp } from "#lib/catalog-sync.ts";
  import { sourceText } from "#lib/settings-fields.ts";

  let settings = $state<SettingOut[] | null>(null);
  let settingsFailure = $state<string | null>(null);
  let schedule = $state("");
  let cutoff = $state("");
  let saving = $state(false);
  let saveMessage = $state<string | null>(null);
  let serverProblem = $state<string | null>(null);

  const scheduleSetting = $derived(settings?.find((s) => s.key === "catalog_sync"));
  const cutoffSetting = $derived(settings?.find((s) => s.key === "similarity_cutoff"));
  const savedSchedule = $derived(scheduleSetting?.value ?? "");
  const savedCutoff = $derived(cutoffValue(cutoffSetting?.value ?? null));
  const problem = $derived(cutoffProblem(cutoff) ?? serverProblem);
  const changed = $derived({
    ...(schedule !== savedSchedule ? { catalog_sync: schedule } : {}),
    ...(cutoff !== savedCutoff ? { similarity_cutoff: cutoff } : {}),
  });
  const dirty = $derived(Object.keys(changed).length > 0);

  function show(next: SettingOut[]): void {
    settings = next;
    schedule = next.find((s) => s.key === "catalog_sync")?.value ?? "";
    cutoff = cutoffValue(next.find((s) => s.key === "similarity_cutoff")?.value ?? null);
  }

  async function load(): Promise<void> {
    try {
      show((await getSettings("catalog")).settings);
      settingsFailure = null;
    } catch (error) {
      settingsFailure = describeError(error);
    }
  }

  $effect(() => {
    void load();
  });

  function pick(value: string): void {
    schedule = value;
    saveMessage = null;
  }

  function typed(text: string): void {
    cutoff = text.trim();
    serverProblem = null;
    saveMessage = null;
  }

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!dirty || problem) return;
    saving = true;
    saveMessage = null;
    try {
      show((await saveSettings("catalog", changed)).settings);
      saveMessage = "Saved. The Catalog page uses the new cutoff now.";
    } catch (error) {
      const byField = settingProblems(error);
      if (byField?.similarity_cutoff) {
        serverProblem = `Similarity cutoff: ${byField.similarity_cutoff}.`;
      } else if (byField?.catalog_sync) {
        saveMessage = `Automatic sync: ${byField.catalog_sync}.`;
      } else {
        saveMessage = describeError(error);
      }
    } finally {
      saving = false;
    }
  }
</script>

{#if settingsFailure}
  <p role="alert" class="error">{settingsFailure}</p>
{:else if !settings}
  <p class="muted">Loading…</p>
{:else}
  <form onsubmit={save} novalidate aria-label="Catalog">
    <div class="fields">
      {#if scheduleSetting}
        <div class="setting">
          <div class="stop">
            <span class="flabel" id="catalog-sync-l">Automatic sync</span>
            <span class="source" class:app={scheduleSetting.source === "app"}
              >{sourceText(scheduleSetting)}</span
            >
          </div>
          <div
            class="seg"
            role="group"
            aria-labelledby="catalog-sync-l"
            aria-describedby="catalog-sync-help"
          >
            {#each SCHEDULES as option (option.value)}
              <button
                type="button"
                aria-pressed={schedule === option.value}
                disabled={saving}
                onclick={() => pick(option.value)}>{option.label}</button
              >
            {/each}
          </div>
          <p class="help muted" id="catalog-sync-help">{scheduleHelp(schedule)}</p>
        </div>
      {/if}
      {#if cutoffSetting}
        <div class="setting">
          <div class="stop">
            <label class="flabel" for="catalog-cutoff">Similarity cutoff</label>
            <span class="source" class:app={cutoffSetting.source === "app"}
              >{sourceText(cutoffSetting)}</span
            >
          </div>
          <div class="unit">
            <input
              id="catalog-cutoff"
              type="number"
              inputmode="decimal"
              min="0.5"
              max="50"
              step="0.5"
              aria-describedby="catalog-cutoff-help"
              aria-invalid={problem ? "true" : "false"}
              disabled={saving}
              value={cutoff}
              oninput={(event) => typed(event.currentTarget.value)}
            />
            <span>ΔE</span>
          </div>
          <p class="help muted" id="catalog-cutoff-help">
            Below 2 is barely visible; 2–10 is close; above 25 is clearly different.
          </p>
          {#if problem}<p class="error" role="alert">{problem}</p>{/if}
        </div>
      {/if}
    </div>
    <div class="buttons">
      <button type="submit" class="primary" disabled={saving || !dirty || !!problem}>Save</button>
      {#if saveMessage}<span class="muted" role="status">{saveMessage}</span>{/if}
    </div>
  </form>
{/if}

<style>
  form {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .fields {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 18px 20px;
  }

  .setting {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .stop {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .flabel {
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
  }

  .source {
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--chip);
    color: var(--muted);
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
  }

  .source.app {
    background: var(--okbg);
    color: var(--oktext);
  }

  .seg {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 4px;
    padding: 4px;
    border-radius: 12px;
    background: var(--chip);
  }

  .seg button {
    border: 0;
    background: transparent;
    color: var(--muted);
  }

  .seg button[aria-pressed="true"] {
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.18);
  }

  .unit {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .unit input {
    flex: 1;
    color: var(--text);
  }

  .unit span {
    font-family: var(--font-mono);
    font-weight: 700;
    color: var(--muted);
  }

  .help,
  .error {
    margin: 0;
    font-size: 13px;
  }

  .buttons {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }
</style>
