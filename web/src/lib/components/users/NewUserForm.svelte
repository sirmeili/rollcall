<script lang="ts">
  import { createUser } from "#lib/api/admin.ts";
  import { describeError } from "#lib/api/errors.ts";
  import type { UserOut } from "#lib/api/types.ts";
  import PasswordMeter from "#lib/components/ui/PasswordMeter.svelte";
  import { passwordOk } from "#lib/password.ts";
  import { ROLE_LABELS, ROLES, type Role } from "#lib/roles.ts";

  interface Props {
    oncreated: (user: UserOut) => void;
    oncancel: () => void;
  }

  let { oncreated, oncancel }: Props = $props();

  let username = $state("");
  let role = $state<Role>("viewer");
  let requester = $state(false);
  let password = $state("");
  let problem = $state<string | null>(null);
  let busy = $state(false);

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!username.trim()) return void (problem = "Enter a username.");
    if (!passwordOk(password)) return void (problem = "The password needs at least 12 characters.");
    busy = true;
    problem = null;
    try {
      oncreated(await createUser(username.trim().toLowerCase(), role, password, requester));
    } catch (error) {
      problem = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<form class="card" onsubmit={submit} aria-labelledby="new-h" novalidate>
  <h2 id="new-h" class="label">New user</h2>
  <div class="row">
    <label class="field">
      Username
      <input
        type="text"
        maxlength="32"
        autocomplete="off"
        autocapitalize="none"
        spellcheck="false"
        bind:value={username}
      />
    </label>
    <label class="field">
      Role
      <select bind:value={role}>
        {#each ROLES as option (option)}<option value={option}>{ROLE_LABELS[option]}</option>{/each}
      </select>
    </label>
    <label class="check">
      <input type="checkbox" bind:checked={requester} aria-describedby="new-req-h" />
      <span>Requester</span>
    </label>
  </div>
  <p class="muted hint" id="new-req-h">A Requester can submit print requests, with any role.</p>
  <label class="field">
    First password
    <input type="password" autocomplete="new-password" maxlength="256" bind:value={password} />
  </label>
  <PasswordMeter {password} />
  <p class="muted hint">They can change it from their account page.</p>
  {#if problem}<p role="alert" class="error">{problem}</p>{/if}
  <div class="actions">
    <button type="submit" class="primary" disabled={busy}>Create</button>
    <button type="button" onclick={oncancel}>Cancel</button>
  </div>
</form>

<style>
  form {
    max-width: 720px;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex: 1 1 220px;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
  }

  .field input,
  .field select {
    color: var(--text);
  }

  .check {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    align-self: flex-end;
    font-size: 14px;
    font-weight: 600;
  }

  .hint {
    margin: 0;
    font-size: 13px;
  }

  .actions {
    display: flex;
    gap: 10px;
  }
</style>
