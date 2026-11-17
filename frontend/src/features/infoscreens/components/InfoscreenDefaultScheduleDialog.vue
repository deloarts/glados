<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'
import { HelpDrawer } from '@/shared/help'
import InfoscreenScheduleEditor from './InfoscreenScheduleEditor.vue'
import { getDisplayScheduleDefault, setDisplayScheduleDefault } from '../api/infoscreensApi'
import {
  isGridValid,
  toScheduleGrid,
  toScheduleRequest,
  type ScheduleGrid,
} from '../utils/displaySchedule'

import type { DisplayScheduleDefault } from '../types/infoscreenResponse'

/**
 * Sets the default display schedule, which every infoscreen set to follow
 * it uses, from the controls bar of the infoscreens page. It loads the
 * stored default each time it opens. Without the permission to write
 * infoscreens the grid opens read only and cannot be saved.
 */
const props = defineProps<{
  /** How many live screens follow the default schedule. */
  followingCount: number
  canWrite: boolean
  /** The tooltip of the disabled Save button, naming the missing permission. */
  missingHint: string
}>()

const emit = defineEmits<{
  saved: [schedule: DisplayScheduleDefault]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()

const schedule = ref<ScheduleGrid | null>(null)
const offOnHolidays = ref(false)
const rounded = ref(false)
const loading = ref(false)
// Whether the stored default arrived; without it nothing may be saved, or
// an unread default would be overwritten.
const loaded = ref(false)
const saving = ref(false)
const errorMessage = ref<string | null>(null)
const explainVisible = ref(false)

watch(visible, async (open) => {
  if (!open) return
  errorMessage.value = null
  loaded.value = false
  loading.value = true
  try {
    const stored = await getDisplayScheduleDefault()
    const grid = toScheduleGrid(stored.display_schedule)
    schedule.value = grid.grid
    rounded.value = grid.rounded
    offOnHolidays.value = stored.off_on_holidays
    loaded.value = true
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('infoscreens.errors.unknown')
  } finally {
    loading.value = false
  }
})

async function onSave(): Promise<void> {
  if (!props.canWrite || !loaded.value) return
  if (!isGridValid(schedule.value)) {
    errorMessage.value = t('infoscreens.errors.schedule')
    return
  }
  errorMessage.value = null
  saving.value = true
  try {
    const saved = await setDisplayScheduleDefault({
      display_schedule: schedule.value ? toScheduleRequest(schedule.value) : null,
      off_on_holidays: offOnHolidays.value,
    })
    visible.value = false
    emit('saved', saved)
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('infoscreens.errors.unknown')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: 'var(--dialog-width-md)' }">
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ t('infoscreens.defaultScheduleDialog.title') }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('infoscreens.scheduleDialog.help')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('infoscreens.scheduleDialog.help')"
          @click="explainVisible = true"
        />
      </div>
    </template>

    <div class="schedule-dialog" data-testid="infoscreen-default-schedule-dialog">
      <p class="intro">
        {{ t('infoscreens.defaultScheduleDialog.intro', { count: followingCount }, followingCount) }}
      </p>
      <div v-if="loading" class="loading" data-testid="default-schedule-loading">
        <ProgressSpinner style="width: 2rem; height: 2rem" stroke-width="6" />
      </div>
      <p v-else-if="!loaded" class="empty-note" data-testid="default-schedule-unavailable">
        {{ t('infoscreens.defaultScheduleDialog.unavailable') }}
      </p>
      <InfoscreenScheduleEditor
        v-else
        v-model:schedule="schedule"
        v-model:off-on-holidays="offOnHolidays"
        id-prefix="default-schedule"
        :disabled="!canWrite"
        :rounded="rounded"
        :always-on-hint="t('infoscreens.defaultScheduleDialog.alwaysOnHint')"
      />
    </div>

    <template #footer>
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error">
        {{ errorMessage }}
      </Message>
      <Button
        type="button"
        :label="t('common.cancel')"
        severity="secondary"
        text
        :disabled="saving"
        @click="visible = false"
      />
      <span v-tooltip.top="canWrite ? undefined : missingHint">
        <Button
          :label="t('common.save')"
          icon="mdi mdi-content-save-outline"
          :loading="saving"
          :disabled="!canWrite || !loaded"
          data-testid="default-schedule-save"
          @click="onSave"
        />
      </span>
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="resources/display-schedule" anchor="schedule" />
</template>

<style scoped lang="scss">
.dialog-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.dialog-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.schedule-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.intro {
  margin: 0;
}

.loading {
  display: flex;
  justify-content: center;
  padding: var(--space-4) 0;
}

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}
</style>
