<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAdminSettingsStore, useSettingsSave } from '@/features/admin-settings'
import { Permission } from '@/core/auth/permissions'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import WeeklyHoursGrid from '@/shared/components/WeeklyHoursGrid.vue'
import { copyWeeklyHours, defaultWeeklyHours, type WeeklyHours } from '@/shared/utils/weeklyHours'
import { getDefaultWorkingHours, setDefaultWorkingHours } from '../api/defaultWorkingHours'
import { HelpButton } from '@/shared/help'

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const settingsStore = useAdminSettingsStore()
const { toastOnError } = useErrorToast()

// Editing the default calendar is machine work, so it needs the machines
// right, not the settings right.
const { missing } = useMissingPermission()
const blockedReason = missing(Permission.WRITE_MACHINES)

// A ref, since WeeklyHoursGrid replaces the whole week on every edit.
const hours = ref<WeeklyHours>(defaultWeeklyHours())

watch(visible, (isVisible) => {
  if (!isVisible) return
  getDefaultWorkingHours()
    .then((week) => {
      hours.value = copyWeeklyHours(week)
    })
    .catch(toastOnError())
})

const { saving, onSave } = useSettingsSave(async () => {
  const saved = await setDefaultWorkingHours(copyWeeklyHours(hours.value))
  // Keeps the production settings tab in step when it was loaded already.
  if (settingsStore.settings?.production) {
    settingsStore.settings.production.default_weekly_hours = copyWeeklyHours(saved)
  }
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <template #header>
      <div class="default-calendar-header">
        <span class="p-dialog-title">{{ t('productionMachines.calendar.defaultTitle') }}</span>
        <span class="default-calendar-help">
          <HelpButton slug="resources/machines" anchor="working-hours" icon="mdi mdi-help" rounded />
        </span>
      </div>
    </template>
    <p class="hint">{{ t('productionMachines.calendar.defaultHint') }}</p>
    <WeeklyHoursGrid v-model:hours="hours" :disabled="!!blockedReason" />

    <template #footer>
      <Button
        :label="t('common.save')"
        icon="mdi mdi-content-save"
        :loading="saving"
        :disabled="!!blockedReason"
        v-tooltip.top="blockedReason || undefined"
        @click="onSave"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.default-calendar-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.default-calendar-help :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.hint {
  margin: 0 0 var(--space-4);
}
</style>
