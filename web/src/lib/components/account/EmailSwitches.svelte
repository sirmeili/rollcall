<script lang="ts">
  import { updateAccount } from "#lib/api/admin.ts";
  import { describeError } from "#lib/api/errors.ts";
  import type { Me } from "#lib/api/types.ts";
  import { session } from "#lib/auth/session.svelte.ts";

  /** The signed-in user's email switches: emails about their own requests for everyone, and
   * about each new request for Admins. Each saves as soon as it is changed. */
  type Switch = "email_on_request_change" | "email_on_new_request";

  const SWITCHES: { key: Switch; label: string; about: string; adminOnly: boolean }[] = [
    {
      key: "email_on_request_change",
      label: "Email me when my requests change",
      about: "your requests change",
      adminOnly: false,
    },
    {
      key: "email_on_new_request",
      label: "Email me when a request is submitted",
      about: "a request is submitted",
      adminOnly: true,
    },
  ];

  let problem = $state<string | null>(null);
  let done = $state<string | null>(null);
  let busy = $state(false);

  const shown = $derived(SWITCHES.filter((s) => !s.adminOnly || session.user?.role === "admin"));

  async function change(key: Switch, about: string, box: HTMLInputElement): Promise<void> {
    const on = box.checked;
    busy = true;
    problem = done = null;
    try {
      const user: Me = await updateAccount({ [key]: on });
      session.user = user;
      done = user[key] ? `You'll be emailed when ${about}.` : `You won't be emailed when ${about}.`;
    } catch (error) {
      box.checked = !on;
      problem = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<section class="card" aria-labelledby="email-switches-h">
  <h2 id="email-switches-h" class="label">Emails</h2>
  {#each shown as s (s.key)}
    <label class="check">
      <input
        type="checkbox"
        checked={session.user?.[s.key] ?? false}
        disabled={busy}
        onchange={(e) => change(s.key, s.about, e.currentTarget)}
      />
      {s.label}
    </label>
  {/each}
  {#if session.user && !session.user.email_set_up}
    <p class="muted">Email isn't set up on this server.</p>
  {/if}
  {#if problem}<p role="alert" class="error">{problem}</p>{/if}
  {#if done}<p role="status">{done}</p>{/if}
</section>

<style>
  section {
    max-width: 560px;
  }

  .check {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 44px;
    font-size: 15px;
    font-weight: 600;
  }

  p {
    margin: 0;
    font-size: 14px;
  }
</style>
