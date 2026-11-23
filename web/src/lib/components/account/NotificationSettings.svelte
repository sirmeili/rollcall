<script lang="ts">
  import { updateAccount } from "#lib/api/admin.ts";
  import { describeError } from "#lib/api/errors.ts";
  import type { NotificationSetting } from "#lib/api/types.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import { NOTIFICATION_KINDS, whenSentence } from "#lib/notifications.ts";

  /** The signed-in user's notification settings: one row per kind their role can see, each
   * with an Email switch that saves as soon as it is changed. The switches are unavailable,
   * saying why, while email is off on the server or the user has no address. */

  let problem = $state<string | null>(null);
  let done = $state<string | null>(null);
  let busy = $state(false);

  const rows = $derived(session.user?.notifications.filter((s) => s.channel === "email") ?? []);
  const unavailable = $derived.by(() => {
    if (!session.user) return null;
    if (!session.user.email_set_up) return "Email is off on this server.";
    if (!session.user.email) return "Add an email address to get notifications by email.";
    return null;
  });

  async function change(setting: NotificationSetting, box: HTMLInputElement): Promise<void> {
    const on = box.checked;
    busy = true;
    problem = done = null;
    try {
      const user = await updateAccount({
        notifications: [{ kind: setting.kind, channel: setting.channel, on }],
      });
      session.user = user;
      const when = whenSentence(setting.kind);
      done = on ? `You'll be emailed when ${when}.` : `You won't be emailed when ${when}.`;
    } catch (error) {
      box.checked = !on;
      problem = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<section class="card" aria-labelledby="notifications-h">
  <h2 id="notifications-h" class="label">Notifications</h2>
  <ul>
    {#each rows as setting (setting.kind)}
      {@const kind = NOTIFICATION_KINDS[setting.kind]}
      <li>
        <div class="grow">
          <span class="name">{kind.label}</span>
          <span class="muted">{kind.when}</span>
        </div>
        <label class="check">
          <input
            type="checkbox"
            aria-label={`Email: ${kind.label}`}
            checked={setting.on}
            disabled={busy || unavailable !== null}
            onchange={(e) => change(setting, e.currentTarget)}
          />
          Email
        </label>
      </li>
    {/each}
  </ul>
  {#if unavailable}<p class="muted">{unavailable}</p>{/if}
  {#if problem}<p role="alert" class="error">{problem}</p>{/if}
  {#if done}<p role="status">{done}</p>{/if}
</section>

<style>
  section {
    max-width: 560px;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 52px;
    padding: 8px 0;
    border-top: 1px solid var(--line);
  }

  li:first-child {
    border-top: 0;
  }

  .grow {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .name {
    font-size: 15px;
    font-weight: 600;
  }

  .grow .muted {
    font-size: 13px;
  }

  .check {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    font-size: 14px;
    font-weight: 600;
  }

  p {
    margin: 0;
    font-size: 14px;
  }
</style>
