<script setup lang="ts">
// One production order contributing to an internal lot position on its
// record card: planning and actual times, who started and ended it, pauses,
// the operator's time assessment against the estimate, and completions.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { formatISODateTime, formatPlanned } from '@/core/utils/dates'
import { hasAction } from '@/core/utils/lifecycleActions'
import { formatDecimal } from '@/core/utils/numbers'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { productionOrderStatusSeverity } from '../../../utils/productionOrderStatus'
import { pauseCauseLabelKey } from '../../../utils/pauseCauses'
import { formatPieceMinutes } from '../../utils/timeComparison'

import type { TimeComparisonMetric, TimeComparisonRow } from '../../utils/timeComparison'
import type {
  ManufacturingAssessmentResponse,
  ProductionOrderCompletionResponse,
  ProductionOrderResponse,
} from '../../../types/productionOrdersResponse'

const props = defineProps<{
  row: {
    order: ProductionOrderResponse
    startedBy: string | null
    endedBy: string | null
    duration: string | null
    estimate: string
    assessment: ManufacturingAssessmentResponse | null
    comparison: TimeComparisonRow[] | null
  }
}>()

const emit = defineEmits<{
  open: [order: ProductionOrderResponse]
  reverse: [order: ProductionOrderResponse, completion: ProductionOrderCompletionResponse]
}>()

const { t } = useI18n()
const { hasPermission } = usePermissions()

// A reversal takes back pieces still at the position. The order offers it
// while its status and lot allow one, a held or finished lot does not, and
// of its completions only one that rejected nothing and is not reversed yet
// can be taken back. The backend checks the rest. Without the permission the
// button stays visible but disabled.
const mayReverse = computed(() => hasPermission(Permission.MANAGE_PRODUCTION_ORDERS))
const reverseTooltip = computed(() =>
  mayReverse.value ? undefined : t('production.lots.detail.record.execution.reverseNoPermission'),
)
const reversedIds = computed(
  () =>
    new Set(
      (props.row.order.completions ?? [])
        .map((c) => c.reverses_completion_id)
        .filter((id): id is number => id != null),
    ),
)

function offersReversal(completion: ProductionOrderCompletionResponse): boolean {
  return (
    hasAction(props.row.order, 'reverse_completion') &&
    completion.reverses_completion_id == null &&
    !reversedIds.value.has(completion.id) &&
    completion.quantity_rejected <= 0
  )
}

// A traceability record has to show what QA decided, so a completion with
// rejected pieces spells out its split and scrap reason. An all-accepted
// completion stays a single number.
function completionBreakdown(completion: ProductionOrderCompletionResponse): string | null {
  if (
    completion.quantity_rejected <= 0 &&
    completion.quantity_rework <= 0 &&
    completion.quantity_scrap <= 0
  ) {
    return null
  }
  const parts = [
    `${formatDecimal(completion.quantity_accepted)} ${t('production.lots.detail.record.execution.accepted')}`,
    `${formatDecimal(completion.quantity_rejected)} ${t('production.lots.detail.record.execution.rejected')}`,
  ]
  if (completion.quantity_rework > 0) {
    parts.push(
      `${formatDecimal(completion.quantity_rework)} ${t('production.lots.detail.record.execution.rework')}`,
    )
  }
  if (completion.quantity_scrap > 0) {
    const reason = completion.scrap_reason
      ? ` (${t(`production.scrap.reasons.${completion.scrap_reason}`)})`
      : ''
    parts.push(
      `${formatDecimal(completion.quantity_scrap)} ${t('production.lots.detail.record.execution.scrap')}${reason}`,
    )
  }
  return parts.join(', ')
}

// Minutes per piece keep the two decimals they are assessed in; setup and
// total minutes read fine at one.
function formatMinutes(metric: TimeComparisonMetric, minutes: number): string {
  return metric === 'perPiece' ? formatPieceMinutes(minutes) : formatDecimal(minutes)
}

function formatDiff(
  metric: TimeComparisonMetric,
  minutes: number | null,
  percent: number | null,
): string {
  if (minutes === null) return getEmptyPlaceholder()
  const sign = minutes > 0 ? '+' : ''
  const value = `${sign}${formatMinutes(metric, minutes)} min`
  return percent === null ? value : `${value} (${sign}${formatDecimal(percent)}%)`
}

// Over the estimate reads as a warning and under it as a win.
function diffClass(minutes: number | null): string {
  if (minutes === null || minutes === 0) return ''
  return minutes > 0 ? 'diff-over' : 'diff-under'
}
</script>

<template>
  <div class="order-card">
    <div class="order-card-header">
      <span
        class="field-value field-link"
        role="button"
        tabindex="0"
        @click="emit('open', row.order)"
        @keydown.enter="emit('open', row.order)"
        >{{ row.order.production_order_number }}</span
      >
      <Tag
        :value="t(`production.lots.orderStatus.${row.order.status}`)"
        :severity="productionOrderStatusSeverity[row.order.status]"
      />
      <span class="order-progress"
        >{{ formatDecimal(row.order.quantity_completed) }} /
        {{ formatDecimal(row.order.quantity) }}</span
      >
    </div>

    <div class="order-dates">
      <span v-if="row.order.machine_pool_id" class="field-sublabel">
        <i class="mdi mdi-view-grid-outline" aria-hidden="true" />
        {{ t('production.lots.detail.record.execution.pool') }}:
        {{ row.order.machine_pool_name }}
      </span>
      <span v-if="row.order.machine_id" class="field-sublabel">
        {{ t('production.lots.detail.record.execution.machine') }}:
        {{ row.order.machine_internal_name }}
      </span>
      <span class="field-sublabel">
        {{ t('production.lots.detail.record.execution.planned') }}:
        {{ formatPlanned(row.order.planned_start) }} →
        {{ formatPlanned(row.order.planned_end) }} ({{
          row.order.planned_by?.full_name ?? t('production.lots.plannedDate.autoPlanner')
        }})
      </span>
      <span v-if="row.order.actual_start" class="field-sublabel">
        {{ t('production.lots.detail.record.execution.actual') }}:
        {{ formatPlanned(row.order.actual_start) }} →
        {{ formatPlanned(row.order.actual_end) }}
      </span>
      <span v-if="row.startedBy" class="field-sublabel">
        {{ t('production.lots.detail.record.execution.startedBy') }}: {{ row.startedBy }}
      </span>
      <span v-if="row.endedBy" class="field-sublabel">
        {{ t('production.lots.detail.record.execution.endedBy') }}: {{ row.endedBy }}
      </span>
      <span v-if="row.duration" class="field-sublabel">
        {{ t('production.lots.detail.record.execution.duration') }}: {{ row.duration }}
      </span>
      <span class="field-sublabel">
        {{ t('production.lots.detail.record.execution.estimated') }}: {{ row.estimate }}
      </span>
      <span class="field-sublabel">
        {{ t('production.lots.detail.record.execution.queuePosition') }}:
        {{ row.order.queue_sequence }}
        <template v-if="row.order.pinned">
          · {{ t('production.lots.detail.record.execution.pinned') }}
        </template>
      </span>
      <span v-if="row.order.not_before" class="field-sublabel">
        {{ t('production.lots.detail.record.execution.notBefore') }}:
        {{ formatPlanned(row.order.not_before) }}
      </span>
      <span v-if="row.order.waiting_on_raw_material" class="field-sublabel waiting-flag">
        <i class="mdi mdi-alert" aria-hidden="true" />
        {{ t('productionQueue.card.waitingOnRawMaterial') }}
      </span>
      <span v-if="row.order.note" class="field-sublabel">
        {{ t('production.lots.detail.record.execution.note') }}: {{ row.order.note }}
      </span>
    </div>

    <!-- Pause/resume pairs. Without them a paused-then-resumed order
         reads as one continuous run between actual_start and
         actual_end. -->
    <div v-if="row.order.interruptions?.length" class="interruptions">
      <span class="field-sublabel interruptions-title">
        {{ t('production.lots.detail.record.execution.interruptions') }}
        ({{ row.order.interruptions.length }})
      </span>
      <span
        v-for="(interruption, index) in row.order.interruptions"
        :key="index"
        class="field-sublabel"
      >
        <i class="mdi mdi-pause" aria-hidden="true" />
        {{ t('production.lots.detail.record.execution.pausedAt') }}
        {{ formatISODateTime(interruption.paused_at) }}
        <template v-if="interruption.resumed_at">
          → {{ t('production.lots.detail.record.execution.resumedAt') }}
          {{ formatISODateTime(interruption.resumed_at) }}
        </template>
        <template v-else>
          · {{ t('production.lots.detail.record.execution.stillPaused') }}
        </template>
        <template v-if="interruption.pause_cause">
          · {{ t(pauseCauseLabelKey(interruption.pause_cause)) }}
        </template>
      </span>
    </div>

    <!-- The operator's measured time, asked at final completion. It is not
         derived from actual_start/end, which include pauses and preemption. -->
    <div v-if="row.assessment && row.comparison" class="assessment">
      <span class="section-label">{{
        t('production.lots.detail.record.execution.assessment')
      }}</span>
      <div class="compare-table-wrap">
        <table class="compare-table">
          <thead>
            <tr>
              <th></th>
              <th class="num">
                {{ t('production.lots.detail.record.execution.estimated') }}
              </th>
              <th class="num">{{ t('production.lots.detail.record.execution.actual') }}</th>
              <th class="num">{{ t('production.lots.detail.record.execution.diff') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="cmp in row.comparison" :key="cmp.metric">
              <td>{{ t(`production.lots.detail.record.execution.${cmp.metric}`) }}</td>
              <td class="num">
                {{
                  cmp.estimated === null
                    ? getEmptyPlaceholder()
                    : `${formatMinutes(cmp.metric, cmp.estimated)} min`
                }}
              </td>
              <td class="num">
                {{
                  cmp.actual === null
                    ? getEmptyPlaceholder()
                    : `${formatMinutes(cmp.metric, cmp.actual)} min`
                }}
              </td>
              <td class="num" :class="diffClass(cmp.diffMinutes)">
                {{ formatDiff(cmp.metric, cmp.diffMinutes, cmp.diffPercent) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="order-dates">
        <span class="field-sublabel">
          {{ t('production.lots.detail.record.execution.complexity') }}:
          {{ t(`productionAssessment.complexity.${row.assessment.complexity}`) }}
        </span>
        <span class="field-sublabel">
          {{ t('production.lots.detail.record.execution.assessedBy') }}:
          {{ row.assessment.operator?.full_name ?? getEmptyPlaceholder() }} ({{
            row.assessment.created
          }})
        </span>
        <span v-if="row.assessment.note" class="field-sublabel">
          {{ t('production.lots.detail.record.execution.note') }}: {{ row.assessment.note }}
        </span>
      </div>
    </div>

    <div v-if="row.order.completions?.length" class="completions">
      <div
        v-for="completion in row.order.completions ?? []"
        :key="completion.id"
        class="completion-row"
        :class="{ 'completion-row--reversed': reversedIds.has(completion.id) }"
      >
        <i
          class="mdi"
          :class="completion.reverses_completion_id != null ? 'mdi-undo-variant' : 'mdi-check-bold'"
          aria-hidden="true"
        />
        <span class="field-value">{{ formatDecimal(completion.quantity) }}</span>
        <span class="field-sublabel">{{ completion.completion_date }}</span>
        <span class="field-sublabel">{{
          completion.operator?.full_name ?? getEmptyPlaceholder()
        }}</span>
        <span
          v-if="completion.recorded_by_id !== completion.operator_id"
          class="field-sublabel"
        >
          ({{ t('production.lots.detail.record.execution.recordedBy') }}
          {{ completion.recorded_by?.full_name ?? getEmptyPlaceholder() }})
        </span>
        <span v-if="completionBreakdown(completion)" class="field-sublabel breakdown">
          {{ completionBreakdown(completion) }}
        </span>
        <span v-if="completion.note" class="field-sublabel">, {{ completion.note }}</span>
        <Tag
          v-if="completion.reverses_completion_id != null"
          :value="
            t('production.lots.detail.record.execution.reversalOf', {
              id: completion.reverses_completion_id,
            })
          "
          severity="secondary"
        />
        <Tag
          v-else-if="reversedIds.has(completion.id)"
          :value="t('production.lots.detail.record.execution.reversed')"
          severity="warn"
        />
        <span
          v-if="offersReversal(completion)"
          v-tooltip="reverseTooltip"
          class="reverse-action"
        >
          <Button
            :label="t('production.lots.detail.record.execution.reverse')"
            icon="mdi mdi-undo"
            severity="secondary"
            text
            size="small"
            :disabled="!mayReverse"
            @click="emit('reverse', row.order, completion)"
          />
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.section-label {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

.field-value {
  font-size: var(--font-size-sm);
}

.field-link {
  cursor: pointer;
  width: fit-content;

  &:hover {
    color: var(--p-primary-color);
    text-decoration: underline;
  }
}

.field-sublabel {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.order-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);

  &:not(:last-child) {
    margin-bottom: var(--space-2);
  }
}

.order-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.order-progress {
  margin-left: auto;
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
}

.order-dates {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.completions {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-top: var(--space-1);
  border-top: 1px dashed var(--p-content-border-color);
}

.completion-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.completion-row--reversed .field-value {
  text-decoration: line-through;
}

.reverse-action {
  margin-left: auto;
}

.breakdown {
  flex-basis: 100%;
  padding-left: var(--space-5);
}

.interruptions {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.interruptions-title {
  font-weight: 600;
}

.waiting-flag {
  color: var(--p-orange-500);
}

.assessment {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-top: var(--space-1);
  border-top: 1px dashed var(--p-content-border-color);
}

.compare-table-wrap {
  overflow-y: auto;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.compare-table {
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

.diff-over {
  color: var(--p-orange-500);
}

.diff-under {
  color: var(--p-green-500);
}
</style>
