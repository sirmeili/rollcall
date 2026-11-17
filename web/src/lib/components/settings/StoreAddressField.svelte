<script lang="ts">
  /** The Catalog card's Store address: the Bambu Lab store Find in store searches. */
  import type { SettingOut } from "#lib/api/settings.ts";
  import { sourceText } from "#lib/settings-fields.ts";

  interface Props {
    setting: SettingOut;
    value: string;
    problem: string | null;
    disabled: boolean;
    oninput: (text: string) => void;
  }

  let { setting, value, problem, disabled, oninput }: Props = $props();
</script>

<div class="setting">
  <div class="stop">
    <label class="flabel" for="catalog-store">Store address</label>
    <span class="source" class:app={setting.source === "app"}>{sourceText(setting)}</span>
  </div>
  <input
    id="catalog-store"
    type="url"
    inputmode="url"
    autocomplete="off"
    spellcheck="false"
    aria-describedby="catalog-store-help"
    aria-invalid={problem ? "true" : "false"}
    {disabled}
    {value}
    oninput={(event) => oninput(event.currentTarget.value)}
  />
  <p class="help muted" id="catalog-store-help">
    Find in store searches this store. Only https addresses, no path. Bambu's store picks your
    region from where you are, so change this only if it doesn't.
  </p>
  {#if problem}<p class="error" role="alert">{problem}</p>{/if}
</div>

<style>
  .setting {
    display: flex;
    flex-direction: column;
    gap: 6px;
    grid-column: 1 / -1;
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

  input {
    font-family: var(--font-mono);
    width: 100%;
    max-width: 420px;
  }

  .help,
  .error {
    margin: 0;
    font-size: 13px;
  }
</style>
