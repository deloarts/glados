<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import {
  DEFAULT_DAY_MINUTES,
  DEFAULT_DAY_START,
  MINUTES_PER_DAY,
  WEEKDAYS,
  type WeeklyHours,
  type WorkInterval,
} from '@/shared/utils/weeklyHours'

// Each weekday's first working interval, its local start time and length,
// or closed. Further intervals of a day are kept untouched and noted. Shared
// by the default calendar and the per-machine working-hours override.

interface Props {
  disabled?: boolean
}

withDefaults(defineProps<Props>(), { disabled: false })

const hours = defineModel<WeeklyHours>('hours', { required: true })

const { t } = useI18n()

function intervalsOf(day: number): WorkInterval[] {
  return hours.value[day] ?? []
}

function isClosed(day: number): boolean {
  return intervalsOf(day).length === 0
}

function setFirst(day: number, change: Partial<WorkInterval>): void {
  const [first, ...rest] = intervalsOf(day)
  const base = first ?? { start: DEFAULT_DAY_START, minutes: DEFAULT_DAY_MINUTES }
  hours.value = { ...hours.value, [day]: [{ ...base, ...change }, ...rest] }
}

function toggleClosed(day: number, closed: boolean): void {
  hours.value = {
    ...hours.value,
    [day]: closed ? [] : [{ start: DEFAULT_DAY_START, minutes: DEFAULT_DAY_MINUTES }],
  }
}
</script>

<template>
  <div class="weekly-hours-grid">
    <div class="weekly-hours-row weekly-hours-head">
      <span />
      <span>{{ t('common.weeklyHours.start') }}</span>
      <span>{{ t('common.weeklyHours.minutes') }}</span>
      <span />
    </div>
    <div v-for="day in WEEKDAYS" :key="day" class="weekly-hours-row">
      <span class="weekday-label">{{ t(`common.weekdays.${day}`) }}</span>
      <InputText
        type="time"
        :model-value="intervalsOf(day)[0]?.start ?? DEFAULT_DAY_START"
        :disabled="disabled || isClosed(day)"
        :aria-label="t('common.weeklyHours.start')"
        size="small"
        @update:model-value="(value) => value && setFirst(day, { start: value })"
      />
      <InputNumber
        :model-value="intervalsOf(day)[0]?.minutes ?? 0"
        :disabled="disabled || isClosed(day)"
        :min="0"
        :max="MINUTES_PER_DAY"
        :aria-label="t('common.weeklyHours.minutes')"
        suffix=" min"
        size="small"
        @update:model-value="(value) => setFirst(day, { minutes: (value as number | null) ?? 0 })"
      />
      <div class="day-extras">
        <label class="closed-toggle">
          <Checkbox
            :model-value="isClosed(day)"
            :disabled="disabled"
            binary
            @update:model-value="(checked) => toggleClosed(day, checked as boolean)"
          />
          {{ t('common.closed') }}
        </label>
        <span v-if="intervalsOf(day).length > 1" class="more-intervals">
          {{ t('common.weeklyHours.moreIntervals', { count: intervalsOf(day).length - 1 }) }}
        </span>
      </div>
    </div>
    <p class="weekly-hours-hint">{{ t('common.weeklyHours.hint') }}</p>
  </div>
</template>

<style scoped lang="scss">
.weekly-hours-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.weekly-hours-row {
  display: grid;
  grid-template-columns: 6rem 7rem 8rem auto;
  align-items: center;
  gap: var(--space-3);
}

.weekly-hours-head {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.weekday-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.day-extras {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.closed-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.more-intervals,
.weekly-hours-hint {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.weekly-hours-hint {
  margin: 0;
}
</style>
