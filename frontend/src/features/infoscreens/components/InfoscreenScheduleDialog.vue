<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'
import { HelpDrawer } from '@/shared/help'
import InfoscreenScheduleEditor from './InfoscreenScheduleEditor.vue'
import { updateInfoscreen } from '../api/infoscreensApi'
import {
  isGridValid,
  toScheduleGrid,
  toScheduleRequest,
  type ScheduleGrid,
} from '../utils/displaySchedule'

import type { DisplayScheduleMode, InfoscreenResponse } from '../types/infoscreenResponse'

/**
 * Sets when the displays showing a screen are on, straight from the list:
 * the default schedule, its own or always on. It saves only the mode, and
 * its own schedule and holiday switch when it has one, so the rest of the
 * screen stays as it is. Without the permission to write infoscreens the
 * grid opens read only and cannot be saved.
 */
const props = defineProps<{
  infoscreen: InfoscreenResponse | null
  canWrite: boolean
  /** The tooltip of the disabled Save button, naming the missing permission. */
  missingHint: string
}>()

const emit = defineEmits<{
  saved: [infoscreen: InfoscreenResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()

const mode = ref<DisplayScheduleMode>('default')
const schedule = ref<ScheduleGrid | null>(null)
const offOnHolidays = ref(false)
const rounded = ref(false)
const saving = ref(false)
const errorMessage = ref<string | null>(null)
const explainVisible = ref(false)

watch(visible, (open) => {
  if (!open || !props.infoscreen) return
  const loaded = toScheduleGrid(props.infoscreen.display_schedule)
  mode.value = props.infoscreen.display_schedule_mode
  schedule.value = loaded.grid
  rounded.value = loaded.rounded
  offOnHolidays.value = props.infoscreen.off_on_holidays
  errorMessage.value = null
})

async function onSave(): Promise<void> {
  const infoscreen = props.infoscreen
  if (!infoscreen || !props.canWrite) return
  const own = mode.value === 'own'
  if (own && !isGridValid(schedule.value)) {
    errorMessage.value = t('infoscreens.errors.schedule')
    return
  }
  errorMessage.value = null
  saving.value = true
  try {
    const saved = await updateInfoscreen(infoscreen.id, {
      display_schedule_mode: mode.value,
      ...(own && {
        display_schedule: schedule.value ? toScheduleRequest(schedule.value) : null,
        off_on_holidays: offOnHolidays.value,
      }),
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
        <span class="p-dialog-title">{{ t('infoscreens.scheduleDialog.title') }}</span>
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

    <div v-if="infoscreen" class="schedule-dialog" data-testid="infoscreen-schedule-dialog">
      <p class="intro">
        {{
          t(
            'infoscreens.scheduleDialog.intro',
            { name: infoscreen.name, count: infoscreen.shown_on.length },
            infoscreen.shown_on.length,
          )
        }}
      </p>
      <InfoscreenScheduleEditor
        v-model:mode="mode"
        v-model:schedule="schedule"
        v-model:off-on-holidays="offOnHolidays"
        id-prefix="schedule-dialog"
        :disabled="!canWrite"
        :rounded="rounded"
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
          :disabled="!canWrite"
          data-testid="schedule-dialog-save"
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

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}
</style>
