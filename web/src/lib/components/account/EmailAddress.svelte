<script lang="ts">
  import { updateAccount } from "#lib/api/admin.ts";
  import { describeError } from "#lib/api/errors.ts";
  import { session } from "#lib/auth/session.svelte.ts";

  /** The signed-in user's own email address: optional and never verified. */
  let address = $state(session.user?.email ?? "");
  let problem = $state<string | null>(null);
  let done = $state<string | null>(null);
  let busy = $state(false);

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    busy = true;
    problem = done = null;
    try {
      const user = await updateAccount({ email: address.trim() });
      session.user = user;
      address = user.email ?? "";
      done = user.email ? "Saved your email address." : "Removed your email address.";
    } catch (error) {
      problem = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<form class="card" onsubmit={submit} aria-labelledby="email-h" novalidate>
  <h2 id="email-h" class="label">Email</h2>
  <label class="field">
    Email address
    <input
      type="email"
      autocomplete="email"
      autocapitalize="none"
      spellcheck="false"
      maxlength="254"
      placeholder="name@example.com"
      bind:value={address}
    />
  </label>
  <p class="muted hint">Optional. RollCall uses it to email you. Leave it empty to remove it.</p>
  {#if problem}<p role="alert" class="error">{problem}</p>{/if}
  {#if done}<p role="status">{done}</p>{/if}
  <button type="submit" class="primary" disabled={busy}>Save email address</button>
</form>

<style>
  form {
    max-width: 560px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
  }

  .field input {
    color: var(--text);
  }

  p {
    margin: 0;
    font-size: 14px;
  }

  .hint {
    font-size: 13px;
  }

  button {
    align-self: flex-start;
  }
</style>
