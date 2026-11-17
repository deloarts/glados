<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { AppLocale } from '@/core/i18n'

import { useTickingNow } from '../../composables/useTickingNow'
import type { WidgetConfigOf, WidgetDataOf } from '../../types/infoscreenFeed'
import {
  clockNumbers,
  clockParts,
  holidayLabel,
  longDateLabel,
} from '../../utils/infoscreenFormat'
import AnalogueClockFace from './AnalogueClockFace.vue'
import BinaryClockFace from './BinaryClockFace.vue'
import WidgetFrame from './WidgetFrame.vue'

// Ticks on the device itself every second; only the next holiday comes from
// the feed. The time shows digital, as an analogue face or as a binary
// clock, with or without seconds; date and holiday follow below in every
// style. A config without style or seconds reads as the digital clock
// without seconds.
const props = defineProps<{
  config: WidgetConfigOf<'clock'>
  data: WidgetDataOf<'clock'> | null
}>()

const { t, locale } = useI18n()

const now = useTickingNow()

const style = computed(() => props.config.style ?? 'digital')
const showSeconds = computed(() => props.config.show_seconds ?? false)
const timeParts = computed(() => clockParts(now.value))
const time = computed(() => clockNumbers(now.value))
const dateLabel = computed(() => longDateLabel(now.value, locale.value as AppLocale))
const holiday = computed(() => {
  const next = props.data?.next_holiday
  if (!props.config.show_next_holiday || !next) return null
  return holidayLabel(next, now.value, t)
})
</script>

<template>
  <WidgetFrame :title="config.title">
    <div class="clock-widget">
      <AnalogueClockFace
        v-if="style === 'analogue'"
        :hours="time.hours"
        :minutes="time.minutes"
        :seconds="time.seconds"
        :show-seconds="showSeconds"
      />
      <BinaryClockFace
        v-else-if="style === 'binary'"
        :hours="time.hours"
        :minutes="time.minutes"
        :seconds="time.seconds"
        :show-seconds="showSeconds"
      />
      <div v-else class="clock-time" data-testid="clock-time">
        <span>{{ timeParts.hoursMinutes }}</span>
        <span v-if="showSeconds" class="clock-seconds" data-testid="clock-seconds">
          {{ timeParts.seconds }}
        </span>
      </div>
      <div v-if="config.show_date" class="clock-date" data-testid="clock-date">
        {{ dateLabel }}
      </div>
      <div v-if="holiday" class="clock-holiday" data-testid="clock-holiday">
        <span class="clock-holiday-label">{{ t('infoscreenRuntime.widgets.clock.nextHoliday') }}</span>
        <span class="clock-holiday-name">{{ holiday.name }}</span>
        <span class="clock-holiday-when">{{ holiday.date }} · {{ holiday.when }}</span>
      </div>
    </div>
  </WidgetFrame>
</template>

<style scoped lang="scss">
.clock-widget {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.4em;
  text-align: center;
}

.clock-time {
  display: flex;
  align-items: baseline;
  gap: 0.15em;
  // The vmin size is the fallback where container units are missing.
  // stylelint-disable-next-line declaration-block-no-duplicate-properties
  font-size: clamp(2.5rem, 12vmin, 24rem);
  font-size: clamp(2.5rem, 34cqmin, 24rem);
  font-weight: 700;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.clock-seconds {
  font-size: 0.4em;
  color: var(--p-text-muted-color);
}

.clock-date {
  font-size: 1.4em;
  font-weight: 600;
}

.clock-holiday {
  display: flex;
  flex-direction: column;
  gap: 0.1em;
  margin-top: 0.4em;
}

.clock-holiday-label,
.clock-holiday-when {
  color: var(--p-text-muted-color);
  font-size: 0.9em;
}

.clock-holiday-name {
  font-size: 1.2em;
  font-weight: 600;
}
</style>
