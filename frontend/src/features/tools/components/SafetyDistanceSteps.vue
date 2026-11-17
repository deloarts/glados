<script setup lang="ts">
/**
 * The worked calculation: every intermediate value with its formula, the
 * same formula with the numbers filled in, and the clause it comes from.
 * For a light curtain the reach paths follow, each with its own result.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { fillExpression, formatQuantity, formatRef, messageText, numberOptions } from '../utils/safetyDistance/format'
import type { SafetyDistanceFormat } from '../utils/safetyDistance/format'
import type { SafetyDistanceResult } from '../utils/safetyDistance/types'
import SafetyDistanceText from './SafetyDistanceText.vue'

const props = defineProps<{ result: SafetyDistanceResult }>()

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()
const f: SafetyDistanceFormat = { t, number: (value, digits) => formatNumber(value, numberOptions(digits)) }

const P = 'tools.safetyDistance'

const rows = computed(() =>
  [...props.result.responseTime.steps, ...props.result.steps].map((step) => ({
    step,
    expression: fillExpression(step, f),
    value: formatQuantity(step.value, step.unit, f),
    ref: step.ref ? formatRef(step.ref, f) : '',
    note: step.note ? messageText(step.note, f) : '',
  })),
)

const paths = computed(() =>
  props.result.paths.map((p) => ({
    key: p.path,
    label: t(`${P}.paths.${p.path}`),
    reach: p.reach === null ? '–' : formatQuantity(p.reach, 'mm', f),
    k: p.k === null ? '–' : formatQuantity(p.k, 'mm/s', f),
    s: p.s === null ? t(`${P}.paths.notCovered`) : formatQuantity(p.s, 'mm', f),
    ref: formatRef(p.ref, f),
  })),
)
</script>

<template>
  <section class="sd-steps" data-testid="sd-steps">
    <h3 class="sd-steps-title">{{ t(`${P}.sections.calculation`) }}</h3>
    <p v-if="rows.length === 0" class="sd-steps-empty">{{ t(`${P}.steps.empty`) }}</p>
    <div v-else class="sd-steps-scroll">
      <table class="sd-steps-table">
        <thead>
          <tr>
            <th scope="col">{{ t(`${P}.steps.columns.quantity`) }}</th>
            <th scope="col">{{ t(`${P}.steps.columns.calculation`) }}</th>
            <th scope="col">{{ t(`${P}.steps.columns.source`) }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in rows" :key="index" :data-testid="`sd-step-${row.step.key}`">
            <th scope="row">{{ t(`${P}.steps.${row.step.key}`) }}</th>
            <td>
              <span class="sd-steps-calc">
                <SafetyDistanceText :text="row.step.symbol" />
                <template v-if="row.step.formula"> = <SafetyDistanceText :text="row.step.formula" /></template>
                <template v-if="row.expression"> = {{ row.expression }}</template>
                = <strong>{{ row.value }}</strong>
              </span>
              <small v-if="row.note" class="sd-steps-note"><SafetyDistanceText :text="row.note" /></small>
            </td>
            <td class="sd-steps-ref">{{ row.ref }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <template v-if="paths.length > 0">
      <h4 class="sd-steps-subtitle">{{ t(`${P}.paths.title`) }}</h4>
      <div class="sd-steps-scroll">
        <table class="sd-steps-table sd-steps-table--paths" data-testid="sd-paths">
          <thead>
            <tr>
              <th scope="col">{{ t(`${P}.paths.columns.path`) }}</th>
              <th scope="col">{{ t(`${P}.paths.columns.reach`) }}</th>
              <th scope="col">K</th>
              <th scope="col">S</th>
              <th scope="col">{{ t(`${P}.steps.columns.source`) }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in paths" :key="p.key" :data-testid="`sd-path-${p.key}`">
              <th scope="row">{{ p.label }}</th>
              <td>{{ p.reach }}</td>
              <td>{{ p.k }}</td>
              <td class="sd-steps-s">{{ p.s }}</td>
              <td class="sd-steps-ref">{{ p.ref }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <small class="sd-steps-hint">{{ t(`${P}.paths.hint`) }}</small>
    </template>
  </section>
</template>

<style scoped lang="scss">
.sd-steps {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sd-steps-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.sd-steps-subtitle {
  margin: var(--space-2) 0 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.sd-steps-empty,
.sd-steps-hint {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  line-height: 1.4;
}

.sd-steps-scroll {
  overflow-x: auto;
}

.sd-steps-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;

  th,
  td {
    padding: var(--space-2) var(--space-2);
    text-align: left;
    vertical-align: top;
    border-bottom: 1px solid var(--p-content-border-color);
  }

  thead th {
    font-size: var(--font-size-xs);
    font-weight: 600;
    color: var(--p-text-muted-color);
  }

  tbody th {
    font-weight: 500;
    color: var(--p-text-muted-color);
  }
}

.sd-steps-calc {
  display: block;
}

.sd-steps-note {
  display: block;
  margin-top: var(--space-1);
  color: var(--p-text-muted-color);
  line-height: 1.35;
}

.sd-steps-ref {
  white-space: nowrap;
  color: var(--p-text-muted-color);
}

.sd-steps-s {
  font-weight: 600;
}
</style>
