<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'

import type { MachinePoolResponse, ProductionMachineResponse } from '@/features/production-machines'
import InfoscreenAlignPicker from './InfoscreenAlignPicker.vue'
import InfoscreenWeatherPlacePicker from './InfoscreenWeatherPlacePicker.vue'
import {
  CLOCK_STYLES,
  DELIVERIES_HORIZON_DAYS,
  DETAIL_NEXT_COUNT,
  EXTERNAL_WORK_HORIZON_DAYS,
  EXTERNAL_WORK_LAYOUTS,
  LOTS_DUE_HORIZON_DAYS,
  MESSAGE_SEVERITIES,
  MESSAGE_TEXT_MAX_LENGTH,
  NEXT_COUNT,
  WEATHER_DAYS,
} from '../utils/infoscreenLayouts'

import type { InfoscreenWidgetConfig, WeatherPlace } from '../types/infoscreenResponse'

/**
 * The settings of one widget, a form per widget type. Every change replaces
 * the whole config, so the page editor above keeps one plain object per
 * slot. The machine and pool lists come from the editor, which loads them
 * once for all slots.
 */
defineProps<{
  machines: ProductionMachineResponse[]
  pools: MachinePoolResponse[]
  /** Shows the errors of required fields once the form was submitted. */
  submitted: boolean
  idPrefix: string
}>()

const widget = defineModel<InfoscreenWidgetConfig>('widget', { required: true })

const { t } = useI18n()

function patch(changes: Record<string, unknown>): void {
  widget.value = { ...widget.value, ...changes } as InfoscreenWidgetConfig
}

const machineBoard = computed(() => (widget.value.type === 'machine_board' ? widget.value : null))
const lotsDue = computed(() => (widget.value.type === 'lots_due' ? widget.value : null))
const lateLots = computed(() => (widget.value.type === 'late_lots' ? widget.value : null))
const deliveries = computed(() =>
  widget.value.type === 'deliveries_expected' ? widget.value : null,
)
const externalWork = computed(() => (widget.value.type === 'external_work' ? widget.value : null))

// The methods load the first time an external work widget is edited.
const methodsStore = useFabricationMethodsStore()
const { localize } = useLocalizedText()
watch(
  externalWork,
  (current) => {
    if (current && methodsStore.items.length === 0) void methodsStore.refresh()
  },
  { immediate: true },
)
const methodOptions = computed(() =>
  methodsStore.activeItems.map((method) => ({ value: method.id, label: localize(method.name) })),
)
const externalWorkLayoutOptions = computed(() =>
  EXTERNAL_WORK_LAYOUTS.map((value) => ({
    value,
    label: t(`infoscreens.externalWorkLayouts.${value}`),
  })),
)
const message = computed(() => (widget.value.type === 'message' ? widget.value : null))
const clock = computed(() => (widget.value.type === 'clock' ? widget.value : null))
const machineDetail = computed(() =>
  widget.value.type === 'machine_detail' ? widget.value : null,
)
const products = computed(() => (widget.value.type === 'products' ? widget.value : null))
const projects = computed(() => (widget.value.type === 'projects' ? widget.value : null))
const weather = computed(() => (widget.value.type === 'weather' ? widget.value : null))

function pickPlace(place: WeatherPlace): void {
  patch({
    location_name: place.name,
    region: place.region,
    country_code: place.country_code,
    latitude: place.latitude,
    longitude: place.longitude,
  })
}

// Another country forgets the town, which belonged to the old one.
function pickCountry(countryCode: string): void {
  if (!weather.value || countryCode === weather.value.country_code) return
  patch({ country_code: countryCode, location_name: '', region: null, latitude: 0, longitude: 0 })
}

const clockStyleOptions = computed(() =>
  CLOCK_STYLES.map((value) => ({ value, label: t(`infoscreens.clockStyles.${value}`) })),
)

const severityOptions = computed(() =>
  MESSAGE_SEVERITIES.map((value) => ({ value, label: t(`infoscreens.severities.${value}`) })),
)
</script>

<template>
  <div class="widget-fields">
    <template v-if="machineBoard">
      <div class="field">
        <label :id="`${idPrefix}-machines-label`" :for="`${idPrefix}-machines`">{{ t('infoscreens.widgetFields.machines') }}</label>
        <MultiSelect
          :model-value="machineBoard.machine_ids"
          :input-id="`${idPrefix}-machines`"
          :aria-labelledby="`${idPrefix}-machines-label`"
          :options="machines"
          option-label="internal_name"
          option-value="id"
          :placeholder="t('infoscreens.widgetFields.machinesPlaceholder')"
          display="chip"
          filter
          fluid
          size="small"
          data-testid="widget-machines"
          @update:model-value="patch({ machine_ids: $event })"
        />
      </div>
      <div class="field">
        <label :id="`${idPrefix}-pools-label`" :for="`${idPrefix}-pools`">{{ t('infoscreens.widgetFields.pools') }}</label>
        <MultiSelect
          :model-value="machineBoard.pool_ids"
          :input-id="`${idPrefix}-pools`"
          :aria-labelledby="`${idPrefix}-pools-label`"
          :options="pools"
          option-label="name"
          option-value="id"
          :placeholder="t('infoscreens.widgetFields.poolsPlaceholder')"
          display="chip"
          filter
          fluid
          size="small"
          @update:model-value="patch({ pool_ids: $event })"
        />
        <small class="hint">{{ t('infoscreens.widgetFields.machineBoardHint') }}</small>
      </div>
      <div class="field">
        <label :for="`${idPrefix}-next`">{{ t('infoscreens.widgetFields.nextCount') }}</label>
        <InputNumber
          :model-value="machineBoard.next_count"
          :input-id="`${idPrefix}-next`"
          :min="NEXT_COUNT.min"
          :max="NEXT_COUNT.max"
          show-buttons
          size="small"
          fluid
          @update:model-value="patch({ next_count: $event ?? NEXT_COUNT.default })"
        />
      </div>
    </template>

    <template v-else-if="lotsDue">
      <div class="field">
        <label :for="`${idPrefix}-horizon`">{{ t('infoscreens.widgetFields.horizonDays') }}</label>
        <InputNumber
          :model-value="lotsDue.horizon_days"
          :input-id="`${idPrefix}-horizon`"
          :min="LOTS_DUE_HORIZON_DAYS.min"
          :max="LOTS_DUE_HORIZON_DAYS.max"
          show-buttons
          size="small"
          fluid
          @update:model-value="patch({ horizon_days: $event ?? LOTS_DUE_HORIZON_DAYS.default })"
        />
      </div>
      <div class="field">
        <label :id="`${idPrefix}-pools-label`" :for="`${idPrefix}-pools`">{{ t('infoscreens.widgetFields.pools') }}</label>
        <MultiSelect
          :model-value="lotsDue.pool_ids"
          :input-id="`${idPrefix}-pools`"
          :aria-labelledby="`${idPrefix}-pools-label`"
          :options="pools"
          option-label="name"
          option-value="id"
          :placeholder="t('infoscreens.widgetFields.allPools')"
          display="chip"
          filter
          fluid
          size="small"
          @update:model-value="patch({ pool_ids: $event })"
        />
      </div>
      <label class="check-row">
        <Checkbox
          :model-value="lotsDue.show_customer"
          binary
          @update:model-value="patch({ show_customer: $event })"
        />
        {{ t('infoscreens.widgetFields.showCustomer') }}
      </label>
    </template>

    <template v-else-if="lateLots">
      <label class="check-row">
        <Checkbox
          :model-value="lateLots.show_customer"
          binary
          @update:model-value="patch({ show_customer: $event })"
        />
        {{ t('infoscreens.widgetFields.showCustomer') }}
      </label>
    </template>

    <template v-else-if="deliveries">
      <div class="field">
        <label :for="`${idPrefix}-horizon`">{{ t('infoscreens.widgetFields.horizonDays') }}</label>
        <InputNumber
          :model-value="deliveries.horizon_days"
          :input-id="`${idPrefix}-horizon`"
          :min="DELIVERIES_HORIZON_DAYS.min"
          :max="DELIVERIES_HORIZON_DAYS.max"
          show-buttons
          size="small"
          fluid
          @update:model-value="patch({ horizon_days: $event ?? DELIVERIES_HORIZON_DAYS.default })"
        />
        <small class="hint">{{ t('infoscreens.widgetFields.deliveriesHint') }}</small>
      </div>
      <label class="check-row">
        <Checkbox
          :model-value="deliveries.show_overdue ?? false"
          binary
          data-testid="widget-deliveries-overdue"
          @update:model-value="patch({ show_overdue: $event })"
        />
        {{ t('infoscreens.widgetFields.showOverdue') }}
      </label>
    </template>

    <template v-else-if="externalWork">
      <div class="field">
        <label :id="`${idPrefix}-layout-label`" :for="`${idPrefix}-layout`">
          {{ t('infoscreens.widgetFields.externalWorkLayout') }}
        </label>
        <Select
          :model-value="externalWork.layout ?? 'days'"
          :input-id="`${idPrefix}-layout`"
          :aria-labelledby="`${idPrefix}-layout-label`"
          :options="externalWorkLayoutOptions"
          option-label="label"
          option-value="value"
          size="small"
          fluid
          data-testid="widget-external-work-layout"
          @update:model-value="patch({ layout: $event })"
        />
      </div>
      <div class="field">
        <label :for="`${idPrefix}-horizon`">{{ t('infoscreens.widgetFields.horizonDays') }}</label>
        <InputNumber
          :model-value="externalWork.horizon_days"
          :input-id="`${idPrefix}-horizon`"
          :min="EXTERNAL_WORK_HORIZON_DAYS.min"
          :max="EXTERNAL_WORK_HORIZON_DAYS.max"
          show-buttons
          size="small"
          fluid
          @update:model-value="patch({ horizon_days: $event ?? EXTERNAL_WORK_HORIZON_DAYS.default })"
        />
        <small class="hint">{{ t('infoscreens.widgetFields.externalWorkHint') }}</small>
      </div>
      <div class="field">
        <label :id="`${idPrefix}-methods-label`" :for="`${idPrefix}-methods`">
          {{ t('infoscreens.widgetFields.methods') }}
        </label>
        <MultiSelect
          :model-value="externalWork.fabrication_method_ids"
          :input-id="`${idPrefix}-methods`"
          :aria-labelledby="`${idPrefix}-methods-label`"
          :options="methodOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('infoscreens.widgetFields.allMethods')"
          display="chip"
          filter
          fluid
          size="small"
          data-testid="widget-external-work-methods"
          @update:model-value="patch({ fabrication_method_ids: $event })"
        />
      </div>
      <label class="check-row">
        <Checkbox
          :model-value="externalWork.show_overdue ?? true"
          binary
          data-testid="widget-external-work-overdue"
          @update:model-value="patch({ show_overdue: $event })"
        />
        {{ t('infoscreens.widgetFields.showOverdueSendOut') }}
      </label>
      <label class="check-row">
        <Checkbox
          :model-value="externalWork.only_with_supplier ?? false"
          binary
          data-testid="widget-external-work-only-with-supplier"
          @update:model-value="patch({ only_with_supplier: $event })"
        />
        {{ t('infoscreens.widgetFields.onlyWithSupplier') }}
      </label>
    </template>

    <template v-else-if="machineDetail">
      <div class="field">
        <label :id="`${idPrefix}-machine-label`" :for="`${idPrefix}-machine`">
          {{ t('infoscreens.widgetFields.machine') }} *
        </label>
        <Select
          :model-value="machineDetail.machine_id || null"
          :input-id="`${idPrefix}-machine`"
          :aria-labelledby="`${idPrefix}-machine-label`"
          :options="machines"
          option-label="internal_name"
          option-value="id"
          :placeholder="t('infoscreens.widgetFields.machinePlaceholder')"
          :invalid="submitted && !machineDetail.machine_id"
          filter
          fluid
          size="small"
          data-testid="widget-machine"
          @update:model-value="patch({ machine_id: $event ?? 0 })"
        />
        <small v-if="submitted && !machineDetail.machine_id" class="field-error">
          {{ t('infoscreens.errors.machine') }}
        </small>
      </div>
      <div class="field">
        <label :for="`${idPrefix}-next`">{{ t('infoscreens.widgetFields.nextCount') }}</label>
        <InputNumber
          :model-value="machineDetail.next_count"
          :input-id="`${idPrefix}-next`"
          :min="DETAIL_NEXT_COUNT.min"
          :max="DETAIL_NEXT_COUNT.max"
          show-buttons
          size="small"
          fluid
          @update:model-value="patch({ next_count: $event ?? DETAIL_NEXT_COUNT.default })"
        />
      </div>
      <label class="check-row">
        <Checkbox
          :model-value="machineDetail.show_drawing ?? true"
          binary
          data-testid="widget-machine-drawing"
          @update:model-value="patch({ show_drawing: $event })"
        />
        {{ t('infoscreens.widgetFields.showDrawing') }}
      </label>
      <label class="check-row">
        <Checkbox
          :model-value="machineDetail.show_customer ?? false"
          binary
          @update:model-value="patch({ show_customer: $event })"
        />
        {{ t('infoscreens.widgetFields.showCustomer') }}
      </label>
    </template>

    <template v-else-if="products">
      <label class="check-row">
        <Checkbox
          :model-value="products.show_projects ?? false"
          binary
          data-testid="widget-products-projects"
          @update:model-value="patch({ show_projects: $event })"
        />
        {{ t('infoscreens.widgetFields.showProjects') }}
      </label>
      <label class="check-row">
        <Checkbox
          :model-value="products.show_customer ?? false"
          binary
          @update:model-value="patch({ show_customer: $event })"
        />
        {{ t('infoscreens.widgetFields.showCustomer') }}
      </label>
    </template>

    <template v-else-if="projects">
      <label class="check-row">
        <Checkbox
          :model-value="projects.show_customer ?? false"
          binary
          @update:model-value="patch({ show_customer: $event })"
        />
        {{ t('infoscreens.widgetFields.showCustomer') }}
      </label>
    </template>

    <template v-else-if="weather">
      <InfoscreenWeatherPlacePicker
        :id-prefix="idPrefix"
        :country-code="weather.country_code"
        :location-name="weather.location_name"
        :region="weather.region ?? null"
        :invalid="submitted && weather.location_name.trim() === ''"
        @country="pickCountry"
        @place="pickPlace"
      />
      <div class="field">
        <label :for="`${idPrefix}-days`">{{ t('infoscreens.widgetFields.weatherDays') }}</label>
        <InputNumber
          :model-value="weather.days"
          :input-id="`${idPrefix}-days`"
          :min="WEATHER_DAYS.min"
          :max="WEATHER_DAYS.max"
          show-buttons
          size="small"
          fluid
          @update:model-value="patch({ days: $event ?? WEATHER_DAYS.default })"
        />
        <small class="hint">{{ t('infoscreens.widgetFields.weatherDaysHint') }}</small>
      </div>
      <label class="check-row">
        <Checkbox
          :model-value="weather.show_wind ?? false"
          binary
          @update:model-value="patch({ show_wind: $event })"
        />
        {{ t('infoscreens.widgetFields.showWind') }}
      </label>
    </template>

    <template v-else-if="message">
      <div class="field">
        <label :for="`${idPrefix}-text`">{{ t('infoscreens.widgetFields.text') }} *</label>
        <Textarea
          :model-value="message.text"
          :id="`${idPrefix}-text`"
          rows="4"
          auto-resize
          fluid
          :maxlength="MESSAGE_TEXT_MAX_LENGTH"
          :invalid="submitted && message.text.trim() === ''"
          data-testid="widget-message-text"
          @update:model-value="patch({ text: $event })"
        />
        <small class="hint">{{ t('infoscreens.widgetFields.markdownHint') }}</small>
        <small v-if="submitted && message.text.trim() === ''" class="field-error">
          {{ t('infoscreens.errors.messageText') }}
        </small>
      </div>
      <div class="field">
        <label :id="`${idPrefix}-severity-label`" :for="`${idPrefix}-severity`">{{ t('infoscreens.widgetFields.severity') }}</label>
        <Select
          :model-value="message.severity"
          :input-id="`${idPrefix}-severity`"
          :aria-labelledby="`${idPrefix}-severity-label`"
          :options="severityOptions"
          option-label="label"
          option-value="value"
          size="small"
          fluid
          data-testid="widget-message-severity"
          @update:model-value="patch({ severity: $event })"
        />
      </div>
      <div class="field">
        <span :id="`${idPrefix}-align-label`" class="form-label">
          {{ t('infoscreens.widgetFields.position') }}
        </span>
        <InfoscreenAlignPicker
          :text-align="message.text_align"
          :vertical-align="message.vertical_align"
          :id-prefix="idPrefix"
          :label="t('infoscreens.widgetFields.position')"
          @pick="patch($event)"
        />
      </div>
    </template>

    <template v-else-if="clock">
      <div class="field">
        <label :id="`${idPrefix}-clock-style-label`" :for="`${idPrefix}-clock-style`">{{ t('infoscreens.widgetFields.clockStyle') }}</label>
        <Select
          :model-value="clock.style"
          :input-id="`${idPrefix}-clock-style`"
          :aria-labelledby="`${idPrefix}-clock-style-label`"
          :options="clockStyleOptions"
          option-label="label"
          option-value="value"
          size="small"
          fluid
          data-testid="widget-clock-style"
          @update:model-value="patch({ style: $event })"
        />
        <small v-if="clock.style === 'binary'" class="hint">
          {{ t('infoscreens.widgetFields.clockBinaryHint') }}
        </small>
      </div>
      <label class="check-row">
        <Checkbox
          :model-value="clock.show_seconds"
          binary
          data-testid="widget-clock-seconds"
          @update:model-value="patch({ show_seconds: $event })"
        />
        {{ t('infoscreens.widgetFields.showSeconds') }}
      </label>
      <label class="check-row">
        <Checkbox
          :model-value="clock.show_date"
          binary
          @update:model-value="patch({ show_date: $event })"
        />
        {{ t('infoscreens.widgetFields.showDate') }}
      </label>
      <label class="check-row">
        <Checkbox
          :model-value="clock.show_next_holiday"
          binary
          @update:model-value="patch({ show_next_holiday: $event })"
        />
        {{ t('infoscreens.widgetFields.showNextHoliday') }}
      </label>
    </template>

    <p v-else class="hint">{{ t('infoscreens.widgetFields.noSettings') }}</p>
  </div>
</template>

<style scoped lang="scss">
.widget-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.form-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.check-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}

.hint {
  margin: 0;
}

.field-error {
  color: var(--p-red-500);
  font-size: var(--font-size-sm);
}
</style>
