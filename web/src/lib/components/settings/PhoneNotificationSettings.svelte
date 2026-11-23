<script lang="ts">
  import SettingsGroupCard from "#lib/components/settings/SettingsGroupCard.svelte";
  import { FIREBASE_FIELDS } from "#lib/settings-fields.ts";
</script>

<SettingsGroupCard
  group="phone-notifications"
  title="Phone notifications"
  intro="With Firebase set up, phones with the google build of the app get phone notifications through Google's push service, with nothing else to install. Without it, phones need a UnifiedPush distributor such as ntfy. docs/deploy.md shows how to make the Firebase project. The service-account key is stored encrypted and never shown again."
  fields={FIREBASE_FIELDS}
  savedText="Saved. Phones get the new settings the next time they open, and restart to use them."
/>
