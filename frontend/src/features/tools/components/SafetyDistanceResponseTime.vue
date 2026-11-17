<script setup lang="ts">
/**
 * Inputs for the overall system response time T: a known value, the sum of
 * its components after equation (3) with a timeline of them, or stopping
 * time measurements after Annex B with their statistics per test condition.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { numberOptions } from '../utils/safetyDistance/format'
import { LIMITS, MAX_SAMPLES } from '../utils/safetyDistance/inputs'
import { RESPONSE_TIME_COMPONENTS, RESPONSE_TIME_METHODS } from '../utils/safetyDistance/types'
import type { ResponseTimeInputs, ResponseTimeResult } from '../utils/safetyDistance/types'
import SafetyDistanceField from './SafetyDistanceField.vue'
import SafetyDistanceNumberList from './SafetyDistanceNumberList.vue'
import SafetyDistanceText from './SafetyDistanceText.vue'
import SafetyDistanceTimelineSketch from './SafetyDistanceTimelineSketch.vue'

defineProps<{ result: ResponseTimeResult }>()

const model = defineModel<ResponseTimeInputs>({ required: true })

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()

const P = 'tools.safetyDistance.responseTime'

function set<K extends keyof ResponseTimeInputs>(key: K, value: ResponseTimeInputs[K]) {
  model.value = { ...model.value, [key]: value }
}

const methodOptions = computed(() =>
  RESPONSE_TIME_METHODS.map((value) => ({ value, label: t(`${P}.methods.${value}`) })),
)

const COMPONENT_SYMBOLS: Record<(typeof RESPONSE_TIME_COMPONENTS)[number], string> = {
  tI: 't_I',
  tL: 't_L',
  tO: 't_O',
  tD: 't_D',
  tR: 't_R',
  tM: 't_M',
  tF: 't_F',
  tS: 't_S',
}

function seconds(value: number | null): string {
  return value === null ? '–' : `${formatNumber(value, numberOptions(4))} s`
}
</script>

<template>
  <div class="sd-rt">
    <div class="sd-rt-method">
      <span id="sd-rt-method-label" class="sd-rt-label">{{ t(`${P}.method`) }}</span>
      <SelectButton
        :model-value="model.method"
        :options="methodOptions"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        aria-labelledby="sd-rt-method-label"
        data-testid="sd-rt-method"
        @update:model-value="set('method', $event)"
      />
    </div>

    <div v-if="model.method === 'direct'" class="sd-rt-grid">
      <SafetyDistanceField
        id="sd-t"
        :model-value="model.direct"
        :label="t(`${P}.direct.label`)"
        symbol="T"
        unit="s"
        :hint="t(`${P}.direct.hint`)"
        :min="LIMITS.time.min"
        :max="LIMITS.time.max"
        :digits="4"
        @update:model-value="set('direct', $event)"
      />
    </div>

    <template v-else-if="model.method === 'components'">
      <div class="sd-rt-grid">
        <SafetyDistanceField
          v-for="component in RESPONSE_TIME_COMPONENTS"
          :id="`sd-${component}`"
          :key="component"
          :model-value="model[component]"
          :label="t(`${P}.components.${component}`)"
          :symbol="COMPONENT_SYMBOLS[component]"
          unit="s"
          :min="LIMITS.time.min"
          :max="LIMITS.time.max"
          :digits="4"
          @update:model-value="set(component, $event)"
        />
      </div>
      <small class="sd-rt-hint">{{ t(`${P}.componentsHint`) }}</small>
      <SafetyDistanceTimelineSketch :inputs="model" />
    </template>

    <template v-else>
      <div class="sd-rt-grid sd-rt-grid--samples">
        <SafetyDistanceNumberList
          id="sd-cold"
          :model-value="model.cold"
          :label="t(`${P}.conditions.cold`)"
          unit="s"
          :min="LIMITS.time.min"
          :max="LIMITS.time.max"
          :max-count="MAX_SAMPLES"
          multiline
          @update:model-value="set('cold', $event)"
        />
        <SafetyDistanceNumberList
          id="sd-warm"
          :model-value="model.warm"
          :label="t(`${P}.conditions.warm`)"
          unit="s"
          :min="LIMITS.time.min"
          :max="LIMITS.time.max"
          :max-count="MAX_SAMPLES"
          multiline
          @update:model-value="set('warm', $event)"
        />
        <SafetyDistanceField
          id="sd-tf"
          :model-value="model.tF"
          :label="t(`${P}.tolerance.label`)"
          symbol="t_F"
          unit="s"
          :hint="t(`${P}.tolerance.hint`)"
          :min="LIMITS.time.min"
          :max="LIMITS.time.max"
          :digits="4"
          @update:model-value="set('tF', $event)"
        />
      </div>
      <small class="sd-rt-hint">{{ t(`${P}.samplesHint`) }}</small>

      <div v-if="result.conditions.length > 0" class="sd-rt-stats">
        <div class="sd-rt-stats-title">
          {{ t(`${P}.statsTitle`) }}
          <SafetyDistanceText :text="t(`${P}.statsFormula`)" class="sd-rt-stats-formula" />
        </div>
        <table class="sd-rt-table" data-testid="sd-rt-stats">
          <thead>
            <tr>
              <th scope="col">{{ t(`${P}.stats.condition`) }}</th>
              <th scope="col">n</th>
              <th scope="col"><SafetyDistanceText text="x_max" /></th>
              <th scope="col">x̄</th>
              <th scope="col"><SafetyDistanceText text="s_x" /></th>
              <th scope="col"><SafetyDistanceText text="x̄ + 3 · s_x" /></th>
              <th scope="col">T</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in result.conditions" :key="c.condition">
              <th scope="row">{{ t(`${P}.conditions.${c.condition}`) }}</th>
              <td>{{ c.n }}</td>
              <td>{{ seconds(c.max) }}</td>
              <td>{{ seconds(c.mean) }}</td>
              <td>{{ seconds(c.sd) }}</td>
              <td>{{ seconds(c.meanPlus3Sd) }}</td>
              <td class="sd-rt-table-t" :data-testid="`sd-rt-${c.condition}`">{{ seconds(c.t) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.sd-rt {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.sd-rt-method {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.sd-rt-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.sd-rt-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: var(--space-3) var(--space-4);
  align-items: start;
}

.sd-rt-grid--samples {
  grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
}

.sd-rt-hint {
  color: var(--p-text-muted-color);
  line-height: 1.35;
}

.sd-rt-stats {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  overflow-x: auto;
}

.sd-rt-stats-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.sd-rt-stats-formula {
  margin-left: var(--space-2);
  font-weight: 400;
  color: var(--p-text-muted-color);
}

.sd-rt-table {
  border-collapse: collapse;
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;

  th,
  td {
    padding: var(--space-1) var(--space-2);
    text-align: right;
    border-bottom: 1px solid var(--p-content-border-color);
    white-space: nowrap;
  }

  th[scope='row'],
  thead th:first-child {
    text-align: left;
  }

  thead th {
    font-size: var(--font-size-xs);
    color: var(--p-text-muted-color);
  }
}

.sd-rt-table-t {
  font-weight: 700;
}
</style>
