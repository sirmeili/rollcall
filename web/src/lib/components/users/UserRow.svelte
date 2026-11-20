<script lang="ts">
  import type { UserChanges } from "#lib/api/admin.ts";
  import type { UserOut } from "#lib/api/types.ts";
  import { dateTime } from "#lib/format.ts";
  import { passwordOk } from "#lib/password.ts";
  import { ROLE_LABELS, ROLES, type Role } from "#lib/roles.ts";

  interface Props {
    user: UserOut;
    /** The signed-in admin's own row: only the email address changes, so nobody locks
     * themselves out. */
    you: boolean;
    busy: boolean;
    onchange: (user: UserOut, changes: UserChanges, done: string) => void;
  }

  let { user, you, busy, onchange }: Props = $props();

  let resetting = $state(false);
  let password = $state("");
  let editingEmail = $state(false);
  let email = $state("");

  function editEmail(): void {
    email = user.email ?? "";
    editingEmail = true;
  }

  function saveEmail(event: SubmitEvent): void {
    event.preventDefault();
    const value = email.trim();
    onchange(
      user,
      { email: value },
      value
        ? `Saved the email address for ${user.username}.`
        : `Removed the email address for ${user.username}.`,
    );
    editingEmail = false;
  }

  function reset(event: SubmitEvent): void {
    event.preventDefault();
    if (!passwordOk(password)) return;
    onchange(user, { password }, `Reset the password for ${user.username}.`);
    resetting = false;
    password = "";
  }
</script>

<tr class:off={user.disabled}>
  <td>
    <div class="who">
      <span class="av" aria-hidden="true">{user.username.charAt(0).toUpperCase()}</span>
      <span class="name">{user.username}</span>
      {#if you}<span class="pill">You</span>{/if}
      {#if user.requester}
        <span class="pill req"
          ><svg
            width="11"
            height="11"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.8"
            aria-hidden="true"
            ><path d="M6 9V3h12v6"></path><rect x="3" y="9" width="18" height="8" rx="2"
            ></rect><path d="M7 17v4h10v-4"></path></svg
          >Requester</span
        >
      {/if}
      {#if user.disabled}<span class="pill dis">Disabled</span>{/if}
    </div>
    <p class="email" class:none={!user.email}>{user.email ?? "No email address"}</p>
  </td>
  <td>
    <div class="rolecell">
      <label>
        <span class="sr-only">Role for {user.username}</span>
        <select
          value={user.role}
          disabled={you || busy}
          onchange={(e) => {
            const role = e.currentTarget.value as Role;
            onchange(user, { role }, `${user.username} is now ${ROLE_LABELS[role]}.`);
          }}
        >
          {#each ROLES as option (option)}<option value={option}>{ROLE_LABELS[option]}</option
            >{/each}
        </select>
      </label>
      <!-- Not disabled on your own row: Requester never touches the role, so it can't lock
         anyone out. -->
      <label class="check">
        <input
          type="checkbox"
          checked={user.requester}
          disabled={busy}
          onchange={(e) => {
            const requester = e.currentTarget.checked;
            onchange(
              user,
              { requester },
              requester
                ? `${user.username} can now submit print requests.`
                : `${user.username} can no longer submit print requests. They can still open their earlier requests and download the files, but can't edit them.`,
            );
          }}
        />
        <span>Requester <span class="sr-only">({user.username})</span></span>
      </label>
    </div>
  </td>
  <td class="date">{user.last_login_at ? dateTime(user.last_login_at) : "Never"}</td>
  <td>
    {#if editingEmail}
      <form class="reset" onsubmit={saveEmail}>
        <label>
          <span class="sr-only">Email address for {user.username}</span>
          <input
            type="email"
            autocomplete="off"
            autocapitalize="none"
            spellcheck="false"
            placeholder="name@example.com"
            maxlength="254"
            bind:value={email}
          />
        </label>
        <button type="submit" class="small primary" disabled={busy}>Save</button>
        <button type="button" class="small" onclick={() => (editingEmail = false)}>Cancel</button>
      </form>
    {:else if resetting && !you}
      <form class="reset" onsubmit={reset}>
        <label>
          <span class="sr-only">New password for {user.username}</span>
          <input
            type="password"
            autocomplete="new-password"
            placeholder="New password, 12+ characters"
            maxlength="256"
            bind:value={password}
          />
        </label>
        <button type="submit" class="small primary" disabled={busy || !passwordOk(password)}
          >Set</button
        >
        <button type="button" class="small" onclick={() => (resetting = false)}>Cancel</button>
      </form>
    {:else}
      <div class="actions">
        <button type="button" class="small" disabled={busy} onclick={editEmail}
          >{user.email ? "Change email" : "Set email"}</button
        >
        {#if !you}
          <button type="button" class="small" disabled={busy} onclick={() => (resetting = true)}
            >Reset password</button
          >
          {#if user.disabled}
            <button
              type="button"
              class="small"
              disabled={busy}
              onclick={() => onchange(user, { disabled: false }, `Enabled ${user.username}.`)}
              >Enable</button
            >
          {:else}
            <button
              type="button"
              class="small danger"
              disabled={busy}
              onclick={() =>
                onchange(
                  user,
                  { disabled: true },
                  `Disabled ${user.username} and signed them out.`,
                )}>Disable</button
            >
          {/if}
        {/if}
      </div>
    {/if}
  </td>
</tr>

<style>
  .who {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }

  .av {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: var(--chip);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 14px;
  }

  .name {
    font-weight: 600;
    font-size: 15px;
  }

  .pill {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--chip);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .pill.req {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: var(--text);
    color: var(--bg);
  }

  .email {
    margin: 4px 0 0 42px;
    font-size: 13px;
    color: var(--muted);
    overflow-wrap: anywhere;
  }

  .email.none {
    font-style: italic;
  }

  .rolecell {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
  }

  .check {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    font-size: 14px;
  }

  .pill.dis {
    background: var(--lowbg);
    color: var(--lowtext);
  }

  tr.off .name {
    color: var(--muted);
  }

  select {
    min-width: 120px;
  }

  .date {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--muted);
    white-space: nowrap;
  }

  .actions,
  .reset {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .reset input {
    min-width: 220px;
  }
</style>
