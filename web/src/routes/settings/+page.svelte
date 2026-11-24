<script lang="ts">
  import CatalogSettings from "#lib/components/settings/CatalogSettings.svelte";
  import EmailSettings from "#lib/components/settings/EmailSettings.svelte";
  import GeneralSettings from "#lib/components/settings/GeneralSettings.svelte";
  import HomeAssistantSettings from "#lib/components/settings/HomeAssistantSettings.svelte";
  import MachineTokens from "#lib/components/settings/MachineTokens.svelte";
  import PhoneNotificationSettings from "#lib/components/settings/PhoneNotificationSettings.svelte";
  import ScannerSettings from "#lib/components/settings/ScannerSettings.svelte";
</script>

<svelte:head><title>Settings · RollCall</title></svelte:head>

<div class="page">
  <div class="pagehead">
    <div>
      <h1>Settings</h1>
      <p>Changes apply at once, without restarting the server. Admins only.</p>
    </div>
  </div>

  <GeneralSettings />
  <ScannerSettings />
  <HomeAssistantSettings />
  <CatalogSettings />
  <EmailSettings />
  <PhoneNotificationSettings />
  <MachineTokens />
</div>
