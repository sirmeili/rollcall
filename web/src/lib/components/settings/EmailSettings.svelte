<script lang="ts">
  import { sendTestEmail } from "#lib/api/settings.ts";
  import EmailStatus from "#lib/components/settings/EmailStatus.svelte";
  import SettingsGroupCard, {
    type TestLine,
  } from "#lib/components/settings/SettingsGroupCard.svelte";
  import { EMAIL_FIELDS } from "#lib/settings-fields.ts";

  /** The Email group: the SMTP server, the Public URL for links, Send test email, and the
   * sender's last success and failure. */
  let version = $state(0);

  async function test(): Promise<TestLine[]> {
    try {
      const result = await sendTestEmail();
      return [{ text: result.message, ok: result.ok }];
    } finally {
      version += 1;
    }
  }
</script>

<SettingsGroupCard
  group="email"
  title="Email"
  intro="The mail server RollCall emails users through. Send test email sends to your own address with the saved settings, so save first. The password is stored encrypted and never shown again."
  fields={EMAIL_FIELDS}
  savedText="Saved. Emails use the new settings."
  {test}
  testLabel="Send test email"
>
  <EmailStatus {version} />
</SettingsGroupCard>
