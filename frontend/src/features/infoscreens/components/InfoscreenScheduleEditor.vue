<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { weekdayName } from '@/core/utils/dates'
import DisplayScheduleGrid from './DisplayScheduleGrid.vue'
import {
  MAX_WINDOWS_PER_DAY,
  SCHEDULE_WEEKDAYS,
  copyMondayToWeekdays,
  defaultGrid,
  filledGrid,
  overfullDays,
  type ScheduleGrid,
} from '../utils/displaySchedule'

import type { DisplayScheduleMode } from '../types/infoscreenResponse'

/**
 * When the displays showing a screen are switched on. Always on keeps them
 * on all the time and stores no schedule; without it the grid sets the half
 * hours in which they are on, in the time of this installation, and they
 * are off in the rest. Switching off on holidays works either way.
 *
 * Bound with a mode, it first asks which schedule a screen follows: the
 * default schedule, its own or none, and shows the grid for its own only.
 * Without a mode it edits one schedule, as the default schedule dialog does.
 */
const props = withDefaults(
  defineProps<{
    idPrefix: string
    disabled?: boolean
    /** Whether a stored window was widened to the half hours around it on loading. */
    rounded?: boolean
    /** The hint under Always on, for when the schedule is not a single screen's. */
    alwaysOnHint?: string
  }>(),
  { disabled: false, rounded: false, alwaysOnHint: undefined },
)

const schedule = defineModel<ScheduleGrid | null>('schedule', { required: true })
const offOnHolidays = defineModel<boolean>('offOnHolidays', { required: true })
const mode = defineModel<DisplayScheduleMode | null>('mode', { default: null })

const { t } = useI18n()

const MODES: DisplayScheduleMode[] = ['default', 'own', 'always_on']
const modeOptions = computed(() =>
  MODES.map((value) => ({ value, label: t(`infoscreens.schedule.modes.${value}`) })),
)
const showsOwn = computed(() => mode.value === null || mode.value === 'own')

function changeMode(value: DisplayScheduleMode | null): void {
  // A select button can be unpressed; the mode always has a value.
  if (value !== null) mode.value = value
}

// Its own schedule is always a grid. A screen switched to it starts with the
// usual working hours; one stored with only the holiday switch, which is on
// on every other day, shows every half hour on.
watch(
  [mode, schedule],
  ([currentMode, current]) => {
    if (currentMode === 'own' && current === null) {
      schedule.value = offOnHolidays.value ? filledGrid(true) : defaultGrid()
    }
  },
  { immediate: true },
)

const alwaysOn = computed({
  get: () => schedule.value === null,
  set: (on: boolean) => {
    schedule.value = on ? null : defaultGrid()
  },
})

const grid = computed({
  get: () => schedule.value ?? filledGrid(false),
  set: (value: ScheduleGrid) => {
    schedule.value = value
  },
})

const invalidDays = computed(() => overfullDays(schedule.value))

function dayName(day: (typeof SCHEDULE_WEEKDAYS)[number]): string {
  // 1 January 2024 was a Monday.
  return weekdayName(new Date(2024, 0, 1 + SCHEDULE_WEEKDAYS.indexOf(day)), 'long')
}

function apply(change: (current: ScheduleGrid) => ScheduleGrid): void {
  if (schedule.value) schedule.value = change(schedule.value)
}
</script>

<template>
  <div class="schedule-editor" :data-testid="`${idPrefix}-schedule`">
    <template v-if="mode !== null">
      <SelectButton
        :model-value="mode"
        :options="modeOptions"
        option-label="label"
        option-value="value"
        size="small"
        :disabled="disabled"
        :aria-label="t('infoscreens.schedule.mode')"
        :data-testid="`${idPrefix}-schedule-mode`"
        @update:model-value="changeMode"
      />
      <small v-if="mode === 'default'" class="hint" :data-testid="`${idPrefix}-schedule-default-hint`">
        {{ t('infoscreens.schedule.defaultHint') }}
      </small>
      <small v-else-if="mode === 'always_on'" class="hint">
        {{ t('infoscreens.schedule.alwaysOnHint') }}
      </small>
    </template>

    <template v-if="showsOwn">
      <label v-if="mode === null" class="check-row">
        <Checkbox
          v-model="alwaysOn"
          binary
          :disabled="disabled"
          :input-id="`${idPrefix}-schedule-always-on`"
          :data-testid="`${idPrefix}-schedule-always-on`"
        />
        {{ t('infoscreens.schedule.alwaysOn') }}
      </label>
      <small v-if="alwaysOn" class="hint">
        {{ props.alwaysOnHint ?? t('infoscreens.schedule.alwaysOnHint') }}
      </small>

      <template v-else>
        <small class="hint">{{ t('infoscreens.schedule.hint') }}</small>
        <Message
          v-if="rounded"
          severity="warn"
          size="small"
          :closable="false"
          :data-testid="`${idPrefix}-schedule-rounded`"
        >
          {{ t('infoscreens.schedule.roundedNote') }}
        </Message>
        <div class="schedule-actions">
          <Button
            type="button"
            icon="mdi mdi-content-copy"
            :label="t('infoscreens.schedule.copyMonday')"
            size="small"
            text
            :disabled="disabled"
            :data-testid="`${idPrefix}-schedule-copy-monday`"
            @click="apply(copyMondayToWeekdays)"
          />
          <Button
            type="button"
            icon="mdi mdi-checkbox-multiple-marked-outline"
            :label="t('infoscreens.schedule.allOn')"
            size="small"
            text
            :disabled="disabled"
            :data-testid="`${idPrefix}-schedule-all-on`"
            @click="apply(() => filledGrid(true))"
          />
          <Button
            type="button"
            icon="mdi mdi-checkbox-multiple-blank-outline"
            :label="t('infoscreens.schedule.allOff')"
            size="small"
            text
            :disabled="disabled"
            :data-testid="`${idPrefix}-schedule-all-off`"
            @click="apply(() => filledGrid(false))"
          />
        </div>
        <DisplayScheduleGrid
          v-model="grid"
          :id-prefix="idPrefix"
          :disabled="disabled"
          :invalid-days="invalidDays"
        />
        <small
          v-for="day in invalidDays"
          :key="day"
          class="field-error"
          :data-testid="`${idPrefix}-schedule-${day}-error`"
        >
          {{ t('infoscreens.schedule.errors.tooMany', { day: dayName(day), max: MAX_WINDOWS_PER_DAY }) }}
        </small>
      </template>

      <label class="check-row">
        <Checkbox
          v-model="offOnHolidays"
          binary
          :disabled="disabled"
          :input-id="`${idPrefix}-off-on-holidays`"
          :data-testid="`${idPrefix}-off-on-holidays`"
        />
        {{ t('infoscreens.schedule.offOnHolidays') }}
      </label>
      <small class="hint">{{ t('infoscreens.schedule.offOnHolidaysHint') }}</small>
    </template>
  </div>
</template>

<style scoped lang="scss">
.schedule-editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.check-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}

.schedule-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.field-error {
  color: var(--p-red-500);
  font-size: var(--font-size-sm);
}
</style>
