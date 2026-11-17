<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import AdminSettingsTabShell from './AdminSettingsTabShell.vue'

// Scaffold: the estimation model has no settings domain on the backend yet,
// so there is nothing to load or save here. The section marks where its
// settings will go; the Save button is kept for layout parity with the other
// tabs and stays disabled until there is something to persist.
const { t } = useI18n()
</script>

<template>
  <AdminSettingsTabShell>
    <template #controls>
      <Toolbar>
        <template #start>
          <Button
            :label="t('common.save')"
            icon="mdi mdi-content-save"
            text
            severity="contrast"
            disabled
          />
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <p class="section-label">
        {{ t('adminSettings.aiModels.productionTimeEstimationSection') }}
      </p>
      <p class="hint">{{ t('adminSettings.aiModels.productionTimeEstimationHint') }}</p>
    </div>
  </AdminSettingsTabShell>
</template>
