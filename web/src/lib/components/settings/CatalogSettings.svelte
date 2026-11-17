<script lang="ts">
  /** The Catalog card: the sync schedule, similarity cutoff and Store address, each
   * source's sync status and Refresh now (docs/mockups/web/SettingsCatalog.html). */
  import CatalogSyncSettings from "#lib/components/settings/CatalogSyncSettings.svelte";
  import CatalogSyncStatus from "#lib/components/settings/CatalogSyncStatus.svelte";
</script>

<section class="card" id="catalog" aria-labelledby="catalog-h">
  <div>
    <h2 id="catalog-h" class="label">Catalog</h2>
    <p class="muted intro">
      Local copies of the Open Filament Database's Bambu Lab colors and BambuStudio's Bambu codes,
      for the Catalog page.
    </p>
  </div>

  <CatalogSyncSettings />

  <div class="divider" aria-hidden="true"></div>

  <CatalogSyncStatus />

  <p class="attrib muted">
    <span>Catalog data from the Open Filament Database, used under the MIT license.</span>
    <span>Bambu codes from BambuStudio's color code list, used under the AGPL-3.0 license.</span>
  </p>
</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 760px;
  }

  .intro {
    margin: 6px 0 0;
    font-size: 14px;
  }

  .attrib {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin: 0;
    font-size: 13px;
  }

  .divider {
    height: 1px;
    background: var(--line);
  }
</style>
