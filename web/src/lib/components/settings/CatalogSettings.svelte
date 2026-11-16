<script lang="ts">
  /** The Catalog card: the sync schedule and similarity cutoff, the sync status and
   * Refresh now (docs/mockups/web/SettingsCatalog.html). */
  import { getSyncStatus, refreshCatalog, type SyncStatus } from "#lib/api/catalog.ts";
  import { describeError } from "#lib/api/errors.ts";
  import {
    getSettings,
    saveSettings,
    settingProblems,
    type SettingOut,
  } from "#lib/api/settings.ts";
  import {
    attemptNote,
    cutoffProblem,
    cutoffValue,
    failureText,
    refreshText,
    SCHEDULES,
    scheduleHelp,
    versionText,
  } from "#lib/catalog-sync.ts";
  import { dateTime } from "#lib/format.ts";
  import { sourceText } from "#lib/settings-fields.ts";

  let status = $state<SyncStatus | null>(null);
  let failure = $state<string | null>(null);
  let message = $state<string | null>(null);
  let busy = $state(false);

  let settings = $state<SettingOut[] | null>(null);
  let settingsFailure = $state<string | null>(null);
  let schedule = $state("");
  let cutoff = $state("");
  let saving = $state(false);
  let saveMessage = $state<string | null>(null);
  let serverProblem = $state<string | null>(null);

  const warning = $derived(status ? failureText(status) : null);
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
      status = await getSyncStatus();
      failure = null;
    } catch (error) {
      failure = describeError(error);
    }
  }

  async function loadSettings(): Promise<void> {
    try {
      show((await getSettings("catalog")).settings);
      settingsFailure = null;
    } catch (error) {
      settingsFailure = describeError(error);
    }
  }

  $effect(() => {
    void load();
    void loadSettings();
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

  async function refresh(): Promise<void> {
    busy = true;
    message = "Checking for a new version…";
    const before = status;
    try {
      status = await refreshCatalog();
      message = refreshText(before, status);
    } catch (error) {
      message = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<section class="card" aria-labelledby="catalog-h">
  <div>
    <h2 id="catalog-h" class="label">Catalog</h2>
    <p class="muted intro">
      A local copy of the Open Filament Database's Bambu Lab colors, for the Catalog page.
    </p>
  </div>

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

  <div class="divider" aria-hidden="true"></div>

  <div class="status" aria-labelledby="catalog-status-h">
    <h3 id="catalog-status-h" class="label">Status</h3>
    {#if failure}
      <p role="alert" class="error">{failure}</p>
    {:else if !status}
      <p class="muted">Loading…</p>
    {:else}
      {#if warning}
        <div class="fail" role="alert">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.4"
            aria-hidden="true"
            ><path
              d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"
            ></path></svg
          >
          <span>{warning}</span>
        </div>
      {/if}
      <dl>
        <div>
          <dt>Last successful sync</dt>
          <dd class="mono">
            {status.last_success_at ? dateTime(status.last_success_at) : "Never"}
          </dd>
        </div>
        <div>
          <dt>Last attempt</dt>
          <dd>
            <span class="mono"
              >{status.last_attempt_at ? dateTime(status.last_attempt_at) : "Never"}</span
            >
            {#if status.last_result}<span class="note">{attemptNote(status)}</span>{/if}
          </dd>
        </div>
        <div>
          <dt>Dataset version</dt>
          <dd class="mono">{versionText(status.dataset_version)}</dd>
        </div>
      </dl>
    {/if}
    <div class="buttons">
      <button type="button" disabled={busy} onclick={refresh}>Refresh now</button>
      {#if message}<span class="muted" role="status">{message}</span>{/if}
    </div>
  </div>

  <p class="attrib muted">
    Catalog data from the Open Filament Database, used under the MIT license.
  </p>
</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 760px;
  }

  .intro {
    margin: 6px 0 0;
    font-size: 14px;
  }

  .status {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  h3 {
    margin: 0;
  }

  dl {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px 20px;
    margin: 0;
  }

  dt {
    font-size: 12px;
    color: var(--muted);
    font-weight: 600;
  }

  dd {
    margin: 3px 0 0;
    font-size: 14px;
    font-weight: 600;
  }

  .mono {
    font-family: var(--font-mono);
  }

  .note {
    display: block;
    font-weight: 500;
    color: var(--muted);
    font-size: 13px;
  }

  .fail {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--lowbg);
    color: var(--lowtext);
    font-size: 14px;
    font-weight: 600;
    line-height: 1.45;
  }

  .fail svg {
    flex: none;
    margin-top: 2px;
  }

  .buttons {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }

  .attrib {
    margin: 0;
    font-size: 13px;
  }

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

  .divider {
    height: 1px;
    background: var(--line);
  }
</style>
