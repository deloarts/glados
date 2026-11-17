<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import { HelpButton } from '@/shared/help'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useQaTasksStore } from '../stores/qaTasksStore'

const { t } = useI18n()
const { hasPermission } = usePermissions()
const tasksStore = useQaTasksStore()

// Read access to the worklist isn't privileged; recording a result is.
// Surfacing that up front beats letting someone work a task and only find
// out at submit (the backend gate is in RecordProductionOrderCompletion).
const canRecord = computed(() => hasPermission(Permission.WRITE_INSPECTIONS))
</script>

<template>
  <ControlsBar>
    <template #start>
      <div class="qa-summary">
        <Tag
          :value="t('productionQa.controls.ready', { n: tasksStore.readyCount })"
          icon="mdi mdi-play-circle-outline"
          severity="success"
        />
        <Tag
          v-if="tasksStore.evidenceMissingCount > 0"
          :value="
            t('productionQa.controls.evidenceMissing', { n: tasksStore.evidenceMissingCount })
          "
          icon="mdi mdi-file-alert-outline"
          severity="warn"
          v-tooltip.top="t('productionQa.controls.evidenceMissingTooltip')"
        />
        <Tag
          v-if="!canRecord"
          :value="t('productionQa.controls.readOnly')"
          icon="mdi mdi-eye-outline"
          severity="secondary"
          v-tooltip.top="t('productionQa.controls.readOnlyTooltip')"
        />
      </div>
    </template>
    <template #handbook>
      <HelpButton rounded />
    </template>
  </ControlsBar>
</template>

<style scoped lang="scss">
.qa-summary {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
</style>
