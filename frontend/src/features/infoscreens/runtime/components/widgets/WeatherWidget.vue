<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { AppLocale } from '@/core/i18n'
import { parseBackendTimestamp, toDayKey } from '@/core/utils/dates'

import { useTickingNow } from '../../composables/useTickingNow'
import type { InfoscreenWeatherDay, WidgetConfigOf, WidgetDataOf } from '../../types/infoscreenFeed'
import {
  daysBetween,
  formatInstantTime,
  formatQuantity,
  weekdayLabel,
} from '../../utils/infoscreenFormat'
import { weatherIcon, weatherKind } from '../../utils/weatherCodes'
import WidgetFrame from './WidgetFrame.vue'

// The weather at the screen's town: now, large, and one column per day
// after it, with the credit the weather service's licence asks for. A
// forecast older than an hour, which stands in while the service does not
// answer, says when it was fetched.
const props = defineProps<{
  config: WidgetConfigOf<'weather'>
  data: WidgetDataOf<'weather'>
}>()

const { t, locale } = useI18n()
const now = useTickingNow(60_000)

const STALE_AFTER_MS = 60 * 60 * 1000

const title = computed(
  () =>
    props.config.title ||
    [props.data.location_name, props.data.region].filter(Boolean).join(', ') ||
    t('infoscreenRuntime.widgets.weather.title'),
)

function degrees(value: number | null | undefined): string {
  if (value === null || value === undefined) return '–'
  return `${Math.round(value)}°`
}

function kindLabel(symbol: string | null | undefined): string {
  return t(`infoscreenRuntime.widgets.weather.kinds.${weatherKind(symbol)}`)
}

// Precipitation in millimetres, left out for a dry day.
function rainLabel(day: InfoscreenWeatherDay): string | null {
  if (day.precipitation_mm === null || day.precipitation_mm < 0.1) return null
  return formatQuantity(day.precipitation_mm, 'mm')
}

// The days after today; today's high and low sit beside the weather now.
const today = computed(() => toDayKey(now.value.toISOString()))
const todayForecast = computed(() =>
  props.data.days.find((day) => daysBetween(today.value, day.date) === 0),
)
const laterDays = computed(() =>
  props.data.days.filter((day) => daysBetween(today.value, day.date) > 0),
)

function dayLabel(day: InfoscreenWeatherDay): string {
  if (daysBetween(today.value, day.date) === 1) {
    return t('infoscreenRuntime.widgets.weather.tomorrow')
  }
  return weekdayLabel(day.date, locale.value as AppLocale)
}

const staleNote = computed(() => {
  const fetched = props.data.fetched_at
  if (!fetched) return null
  const age = now.value.getTime() - parseBackendTimestamp(fetched).getTime()
  if (age < STALE_AFTER_MS) return null
  return t('infoscreenRuntime.widgets.weather.asOf', { time: formatInstantTime(fetched) })
})
</script>

<template>
  <WidgetFrame :title="title">
    <p v-if="data.status === 'off'" class="widget-empty" data-testid="weather-off">
      {{ t('infoscreenRuntime.widgets.weather.off') }}
    </p>
    <p v-else-if="!data.now" class="widget-empty" data-testid="weather-unavailable">
      {{ t('infoscreenRuntime.widgets.weather.unavailable') }}
    </p>
    <div v-else class="weather">
      <div class="weather-now" data-testid="weather-now">
        <i
          class="mdi weather-now-icon"
          :class="weatherIcon(data.now.symbol)"
          aria-hidden="true"
        />
        <div class="weather-now-text">
          <span class="weather-now-temperature">{{ degrees(data.now.temperature) }}</span>
          <span class="weather-now-kind">{{ kindLabel(data.now.symbol) }}</span>
          <span v-if="todayForecast" class="weather-detail">
            {{ degrees(todayForecast.temperature_max) }} /
            {{ degrees(todayForecast.temperature_min) }}
            <template v-if="rainLabel(todayForecast)">
              · <i class="mdi mdi-water" aria-hidden="true" />
              {{ rainLabel(todayForecast) }}
            </template>
          </span>
          <span
            v-if="config.show_wind && data.now.wind_speed !== null"
            class="weather-detail"
            data-testid="weather-wind"
          >
            <i class="mdi mdi-weather-windy" aria-hidden="true" />
            {{ t('infoscreenRuntime.widgets.weather.wind', { speed: Math.round(data.now.wind_speed) }) }}
          </span>
        </div>
      </div>
      <ul v-if="laterDays.length > 0" class="weather-days">
        <li v-for="day in laterDays" :key="day.date" class="weather-day" data-testid="weather-day">
          <span class="weather-day-name">{{ dayLabel(day) }}</span>
          <i
            class="mdi weather-day-icon"
            :class="weatherIcon(day.symbol)"
            :title="kindLabel(day.symbol)"
            aria-hidden="true"
          />
          <span class="weather-day-range">
            {{ degrees(day.temperature_max) }}
            <span class="weather-day-low">{{ degrees(day.temperature_min) }}</span>
          </span>
          <span v-if="rainLabel(day)" class="weather-detail">{{ rainLabel(day) }}</span>
        </li>
      </ul>
      <p class="weather-footer">
        <span v-if="staleNote" data-testid="weather-stale">{{ staleNote }}</span>
        <span v-if="data.attribution" class="weather-credit" data-testid="weather-credit">
          {{ t('infoscreenRuntime.widgets.weather.credit', { source: data.attribution }) }}
        </span>
      </p>
    </div>
  </WidgetFrame>
</template>

<style scoped lang="scss">
.weather {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.8em;
}

.weather-now {
  display: flex;
  align-items: center;
  gap: 0.6em;
  min-width: 0;
}

.weather-now-icon {
  flex: 0 0 auto;
  font-size: 4.5em;
  line-height: 1;
  color: var(--p-primary-color);
}

.weather-now-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.weather-now-temperature {
  font-size: 2.6em;
  font-weight: 700;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.weather-now-kind {
  font-weight: 600;
}

.weather-detail {
  font-size: 0.8em;
  color: var(--p-text-muted-color);
  font-variant-numeric: tabular-nums;
}

.weather-days {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(5em, 1fr));
  gap: 0.4em;
}

.weather-day {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.1em;
  padding: 0.3em;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-sm);
}

.weather-day-name {
  font-size: 0.8em;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.weather-day-icon {
  font-size: 1.8em;
  line-height: 1.1;
}

.weather-day-range {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.weather-day-low {
  font-weight: 400;
  color: var(--p-text-muted-color);
}

.weather-footer {
  display: flex;
  justify-content: space-between;
  gap: 1em;
  margin: 0;
  font-size: 0.7em;
  color: var(--p-text-muted-color);
}

.weather-credit {
  margin-left: auto;
}

.widget-empty {
  margin: 0;
  color: var(--p-text-muted-color);
}
</style>
