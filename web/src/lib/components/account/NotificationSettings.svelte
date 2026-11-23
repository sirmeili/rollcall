<script lang="ts">
  import { updateAccount } from "#lib/api/admin.ts";
  import { describeError } from "#lib/api/errors.ts";
  import type {
    NotificationChannel,
    NotificationKind,
    NotificationSetting,
  } from "#lib/api/types.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import { NOTIFICATION_KINDS, whenSentence } from "#lib/notifications.ts";

  /** The signed-in user's notification settings: one row per kind their role can see, each
   * with an Email and a Phone switch that save as soon as they are changed. The Email
   * switches are unavailable, saying why, while email is off on the server or the user has
   * no address. Without a registered phone, the list says phone notifications need the phone
   * app; the Phone switches can still be chosen ahead. */

  const CHANNELS: { channel: NotificationChannel; label: string }[] = [
    { channel: "email", label: "Email" },
    { channel: "phone", label: "Phone" },
  ];

  let problem = $state<string | null>(null);
  let done = $state<string | null>(null);
  let busy = $state(false);

  /** Each kind, in the server's order, with its setting on each channel. */
  const rows = $derived.by(() => {
    const byKind = new Map<
      NotificationKind,
      Partial<Record<NotificationChannel, NotificationSetting>>
    >();
    for (const setting of session.user?.notifications ?? []) {
      byKind.set(setting.kind, { ...byKind.get(setting.kind), [setting.channel]: setting });
    }
    return [...byKind].map(([kind, settings]) => ({ kind, settings }));
  });
  const emailUnavailable = $derived.by(() => {
    if (!session.user) return null;
    if (!session.user.email_set_up) return "Email is off on this server.";
    if (!session.user.email) return "Add an email address to get notifications by email.";
    return null;
  });
  const noPhone = $derived(session.user !== null && !session.user.phone_registered);

  function saidDone(channel: NotificationChannel, on: boolean, when: string): string {
    if (channel === "phone") {
      return on
        ? `You'll get a phone notification when ${when}.`
        : `You won't get a phone notification when ${when}.`;
    }
    return on ? `You'll be emailed when ${when}.` : `You won't be emailed when ${when}.`;
  }

  async function change(setting: NotificationSetting, box: HTMLInputElement): Promise<void> {
    const on = box.checked;
    busy = true;
    problem = done = null;
    try {
      const user = await updateAccount({
        notifications: [{ kind: setting.kind, channel: setting.channel, on }],
      });
      session.user = user;
      done = saidDone(setting.channel, on, whenSentence(setting.kind));
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
    {#each rows as row (row.kind)}
      {@const kind = NOTIFICATION_KINDS[row.kind]}
      <li>
        <div class="grow">
          <span class="name">{kind.label}</span>
          <span class="muted">{kind.when}</span>
        </div>
        {#each CHANNELS as { channel, label } (channel)}
          {@const setting = row.settings[channel]}
          {#if setting}
            <label class="check">
              <input
                type="checkbox"
                aria-label={`${label}: ${kind.label}`}
                checked={setting.on}
                disabled={busy || (channel === "email" && emailUnavailable !== null)}
                onchange={(e) => change(setting, e.currentTarget)}
              />
              {label}
            </label>
          {/if}
        {/each}
      </li>
    {/each}
  </ul>
  {#if emailUnavailable}<p class="muted">{emailUnavailable}</p>{/if}
  {#if noPhone}<p class="muted">Phone notifications need the phone app.</p>{/if}
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
