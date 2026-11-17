<script setup lang="ts">
// Steps of one lot position on its record card, with the setup, per-piece
// and total time estimates for the position's quantity.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatDecimal } from '@/core/utils/numbers'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { formatMinutesDuration, stepMethodLabel } from '../../../utils/lotStepDisplay'

import type { LotStepResponse } from '../../../types/productionLotsResponse'

const props = defineProps<{
  steps: LotStepResponse[]
  quantity: number
}>()

const { t } = useI18n()

// The step's measured estimate, or the project budget share it falls back
// to until one is measured, flagged so a budgeted guess never reads as a
// measured fact.
function perPieceMinutes(step: LotStepResponse): { value: number | null; fromBudget: boolean } {
  if (step.estimated_minutes_per_piece !== null) {
    return { value: step.estimated_minutes_per_piece, fromBudget: false }
  }
  if (step.time_budget_per_piece !== null) {
    return { value: step.time_budget_per_piece, fromBudget: true }
  }
  return { value: null, fromBudget: false }
}

const stepRows = computed(() =>
  props.steps.map((step) => {
    const perPiece = perPieceMinutes(step)
    return {
      step,
      setup: step.estimated_setup_minutes,
      perPiece: perPiece.value,
      perPieceFromBudget: perPiece.fromBudget,
      // Same formula as the backend's estimated duration: setup plus
      // quantity times per-piece.
      total:
        perPiece.value === null
          ? null
          : (step.estimated_setup_minutes ?? 0) + props.quantity * perPiece.value,
    }
  }),
)
</script>

<template>
  <div class="sub-section">
    <span class="section-label">{{ t('production.lots.detail.record.execution.steps') }}</span>
    <div class="steps-table-wrap">
      <table class="steps-table">
        <thead>
          <tr>
            <th>#</th>
            <th>{{ t('production.lots.detail.record.execution.step') }}</th>
            <th class="num">{{ t('production.lots.detail.record.execution.estSetup') }}</th>
            <th class="num">{{ t('production.lots.detail.record.execution.estPerPiece') }}</th>
            <th class="num">{{ t('production.lots.detail.record.execution.estTotal') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in stepRows" :key="row.step.id">
            <td>{{ row.step.sequence }}</td>
            <td class="step-name-cell">
              <i
                v-if="row.step.role === 'inspection'"
                class="mdi mdi-shield-check-outline step-icon"
                v-tooltip.top="t('production.lots.detail.record.execution.inspectionStep')"
                aria-hidden="true"
              />
              {{ stepMethodLabel(row.step) }}
              <i
                v-if="row.step.inspection_method_requires_evidence"
                class="mdi mdi-paperclip step-icon"
                v-tooltip.top="t('production.lots.detail.record.execution.evidenceRequired')"
                aria-hidden="true"
              />
              <span v-if="row.step.note" class="field-sublabel">, {{ row.step.note }}</span>
            </td>
            <td class="num">
              {{ row.setup === null ? getEmptyPlaceholder() : `${formatDecimal(row.setup)} min` }}
            </td>
            <td class="num">
              <span
                v-if="row.perPiece !== null"
                :class="{ 'from-budget': row.perPieceFromBudget }"
                v-tooltip.top="
                  row.perPieceFromBudget
                    ? t('production.lots.detail.record.execution.fromBudgetTooltip')
                    : undefined
                "
                >{{ formatDecimal(row.perPiece) }} min<template v-if="row.perPieceFromBudget">
                  *</template
                ></span
              >
              <template v-else>{{ getEmptyPlaceholder() }}</template>
            </td>
            <td class="num">
              {{ row.total === null ? getEmptyPlaceholder() : formatMinutesDuration(row.total) }}
            </td>
          </tr>
          <tr v-if="stepRows.length === 0">
            <td colspan="5" class="empty-note">
              {{ t('production.lots.detail.record.execution.noSteps') }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped lang="scss">
.sub-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.section-label {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

.field-sublabel {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.empty-note {
  font-style: italic;
}

.step-icon {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  vertical-align: -0.1em;
}

.steps-table-wrap {
  overflow-y: auto;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  max-height: 10rem;
}

.steps-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-xs);

  th {
    text-align: left;
    font-weight: 600;
    color: var(--p-text-muted-color);
    padding: var(--space-1) var(--space-2);
    border-bottom: 1px solid var(--p-content-border-color);
    position: sticky;
    top: 0;
    background: var(--p-content-background);
  }

  td {
    padding: var(--space-1) var(--space-2);
    border-bottom: 1px solid var(--p-content-border-color);
  }

  tr:last-child td {
    border-bottom: none;
  }

  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
}

.step-name-cell {
  color: var(--p-text-color);
}

// A budget share is a placeholder until someone measures the real figure.
.from-budget {
  color: var(--p-text-muted-color);
  font-style: italic;
  cursor: help;
}
</style>
