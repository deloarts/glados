<script setup lang="ts">
import { getCountryDataList, getEmojiFlag } from 'countries-list'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'

import { searchWeatherPlaces } from '../api/infoscreensApi'
import type { InfoscreenLanguage, WeatherPlace } from '../types/infoscreenResponse'

/**
 * Where the weather widget's forecast is for: a country, then a town in it
 * found by name. Only the town is kept, never an address, so the weather
 * service learns no more than the town's centre. The search runs when asked,
 * never as the user types, as the place search's usage policy requires.
 */
const props = defineProps<{
  idPrefix: string
  countryCode: string
  locationName: string
  region: string | null
  invalid: boolean
}>()

const emit = defineEmits<{
  country: [countryCode: string]
  place: [place: WeatherPlace]
}>()

const { t, locale } = useI18n()

const countryOptions = getCountryDataList()
  .map((c) => ({ label: `${getEmojiFlag(c.iso2)} ${c.name}`, value: c.iso2 }))
  .sort((a, b) => a.label.localeCompare(b.label))

// The country of the app's language until one is picked, so the usual case
// needs no choice at all.
const LOCALE_COUNTRY: Record<string, string> = { deAT: 'AT', enGB: 'GB' }
const country = computed(() => props.countryCode || LOCALE_COUNTRY[locale.value] || 'AT')

const query = ref('')
const results = ref<WeatherPlace[] | null>(null)
const searching = ref(false)
const searchError = ref<string | null>(null)

const selectedLabel = computed(() =>
  props.locationName ? [props.locationName, props.region].filter(Boolean).join(', ') : null,
)

function placeLabel(place: WeatherPlace): string {
  return [place.name, place.region].filter(Boolean).join(', ')
}

// The place search's usage policy allows no search as you type, so it runs
// only on the button or Enter.
async function search(): Promise<void> {
  const text = query.value.trim()
  if (text.length < 2 || searching.value) return
  searching.value = true
  searchError.value = null
  try {
    results.value = await searchWeatherPlaces(text, country.value, locale.value as InfoscreenLanguage)
  } catch (err) {
    results.value = null
    searchError.value = extractApiError(err) ?? t('infoscreens.widgetFields.weatherSearchFailed')
  } finally {
    searching.value = false
  }
}

function pick(place: WeatherPlace): void {
  emit('place', place)
  results.value = null
  query.value = ''
}

function changeCountry(countryCode: string): void {
  results.value = null
  emit('country', countryCode)
}
</script>

<template>
  <div class="weather-place">
    <div class="field">
      <label :id="`${idPrefix}-country-label`" :for="`${idPrefix}-country`">
        {{ t('infoscreens.widgetFields.weatherCountry') }}
      </label>
      <Select
        :model-value="country"
        :input-id="`${idPrefix}-country`"
        :aria-labelledby="`${idPrefix}-country-label`"
        :options="countryOptions"
        option-label="label"
        option-value="value"
        filter
        fluid
        size="small"
        data-testid="widget-weather-country"
        @update:model-value="changeCountry"
      />
    </div>
    <div class="field">
      <label :for="`${idPrefix}-place`">{{ t('infoscreens.widgetFields.weatherPlace') }} *</label>
      <p v-if="selectedLabel" class="place-selected" data-testid="widget-weather-selected">
        <i class="mdi mdi-map-marker" aria-hidden="true" />
        {{ selectedLabel }}
      </p>
      <div class="place-search">
        <InputText
          v-model="query"
          :id="`${idPrefix}-place`"
          :placeholder="t('infoscreens.widgetFields.weatherPlacePlaceholder')"
          :invalid="invalid"
          size="small"
          fluid
          data-testid="widget-weather-query"
          @keydown.enter.prevent="search"
        />
        <Button
          type="button"
          icon="mdi mdi-magnify"
          :label="t('infoscreens.widgetFields.weatherSearch')"
          severity="secondary"
          size="small"
          :loading="searching"
          :disabled="query.trim().length < 2"
          data-testid="widget-weather-search"
          @click="search"
        />
      </div>
      <ul v-if="results && results.length > 0" class="place-results" data-testid="widget-weather-results">
        <li v-for="place in results" :key="`${place.name}-${place.latitude}-${place.longitude}`">
          <Button
            type="button"
            :label="placeLabel(place)"
            text
            size="small"
            class="place-result"
            data-testid="widget-weather-result"
            @click="pick(place)"
          />
        </li>
      </ul>
      <small v-else-if="results" class="hint">{{ t('infoscreens.widgetFields.weatherNoPlaces') }}</small>
      <small v-if="searchError" class="field-error">{{ searchError }}</small>
      <small v-else-if="invalid" class="field-error">
        {{ t('infoscreens.errors.weatherPlace') }}
      </small>
      <small class="hint">{{ t('infoscreens.widgetFields.weatherPlaceHint') }}</small>
    </div>
  </div>
</template>

<style scoped lang="scss">
.weather-place {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.field label {
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.hint {
  display: block;
  margin: 0;
}

.place-selected {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin: 0 0 var(--space-1);
  font-weight: 600;
}

.place-search {
  display: flex;
  gap: var(--space-2);
}

.place-results {
  list-style: none;
  margin: var(--space-1) 0 0;
  padding: 0;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.place-result {
  width: 100%;
  justify-content: flex-start;
}

.field-error {
  color: var(--p-red-500);
  font-size: var(--font-size-sm);
}
</style>
