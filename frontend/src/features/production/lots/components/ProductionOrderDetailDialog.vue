<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { formatPlanned } from '@/core/utils/dates'
import {
  conflictLabelKey,
  conflictSeverity,
  conflictTooltipKey,
} from '../../utils/productionOrderConflicts'
import { formatDecimal } from '@/core/utils/numbers'
import { formatPieceMinutes } from '../utils/timeComparison'
import { formatMinutesDuration } from '../../utils/lotStepDisplay'
import {
  productionOrderPrioritySeverity,
  productionOrderStatusSeverity,
} from '../../utils/productionOrderStatus'
import LotRecordMeta from './lot-detail/LotRecordMeta.vue'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useMadeItemLabel } from '@/features/made-items'

import type {
  ManufacturingAssessmentResponse,
  ProductionOrderResponse,
} from '../../types/productionOrdersResponse'

defineProps<{
  order: ProductionOrderResponse | null
  startedBy: string | null
  endedBy: string | null
  duration: string | null
  assessment: ManufacturingAssessmentResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const { format: madeItemLabel } = useMadeItemLabel()
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="order?.production_order_number ?? ''"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <div v-if="order" class="po-detail">
      <div class="po-detail-tags">
        <Tag
          :value="t(`production.lots.orderStatus.${order.status}`)"
          :severity="productionOrderStatusSeverity[order.status]"
        />
        <Tag
          :value="t(`productionQueue.priority.${order.priority}`)"
          :severity="productionOrderPrioritySeverity[order.priority]"
        />
        <Tag
          v-for="conflict in order.conflicts"
          :key="conflict"
          :value="t(conflictLabelKey(conflict))"
          :severity="conflictSeverity[conflict]"
          icon="mdi mdi-alert"
          v-tooltip.top="t(conflictTooltipKey(conflict))"
        />
      </div>

      <div class="detail-grid">
        <div class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.execution.orderDialog.lot')
          }}</span>
          <span class="field-value">{{ order.lot_number }}</span>
        </div>
        <div class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.execution.orderDialog.item')
          }}</span>
          <span class="field-value">{{
            madeItemLabel(order.made_item_part_number, order.made_item_revision)
          }}</span>
        </div>
        <div class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.execution.orderDialog.position')
          }}</span>
          <span class="field-value">
            {{
              t('production.lots.detail.record.execution.orderDialog.positionValue', {
                sequence: order.lot_position_sequence,
                count: order.lot_position_count,
              })
            }}
          </span>
        </div>
        <div class="field">
          <span class="field-label">{{ t('production.lots.detail.record.execution.qty') }}</span>
          <span class="field-value"
            >{{ formatDecimal(order.quantity_completed) }} /
            {{ formatDecimal(order.quantity) }}</span
          >
        </div>
        <div v-if="order.machine_pool_name" class="field">
          <span class="field-label">{{ t('production.lots.detail.record.execution.pool') }}</span>
          <span class="field-value">{{ order.machine_pool_name }}</span>
        </div>
        <div v-if="order.machine_internal_name" class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.execution.machine')
          }}</span>
          <span class="field-value">{{ order.machine_internal_name }}</span>
        </div>
        <div class="field field-wide">
          <span class="field-label">{{
            t('production.lots.detail.record.execution.planned')
          }}</span>
          <span class="field-value">
            {{ formatPlanned(order.planned_start) }} → {{ formatPlanned(order.planned_end) }} ({{
              order.planned_by?.full_name ?? t('production.lots.plannedDate.autoPlanner')
            }})
          </span>
        </div>
        <div v-if="order.actual_start" class="field field-wide">
          <span class="field-label">{{ t('production.lots.detail.record.execution.actual') }}</span>
          <span class="field-value">
            {{ formatPlanned(order.actual_start) }} → {{ formatPlanned(order.actual_end) }}
          </span>
        </div>
        <div v-if="startedBy" class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.execution.startedBy')
          }}</span>
          <span class="field-value">{{ startedBy }}</span>
        </div>
        <div v-if="endedBy" class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.execution.endedBy')
          }}</span>
          <span class="field-value">{{ endedBy }}</span>
        </div>
        <div v-if="duration" class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.execution.duration')
          }}</span>
          <span class="field-value">{{ duration }}</span>
        </div>
        <div class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.execution.estimated')
          }}</span>
          <span class="field-value">{{
            formatMinutesDuration(order.estimated_duration_minutes)
          }}</span>
        </div>
        <div class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.execution.queuePosition')
          }}</span>
          <span class="field-value">
            {{ order.queue_sequence }}
            <template v-if="order.pinned">
              · {{ t('production.lots.detail.record.execution.pinned') }}
            </template>
          </span>
        </div>
        <div v-if="order.not_before" class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.execution.notBefore')
          }}</span>
          <span class="field-value">{{ formatPlanned(order.not_before) }}</span>
        </div>
        <div v-if="order.waiting_on_raw_material" class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.execution.orderDialog.blocked')
          }}</span>
          <Tag
            :value="t('productionQueue.card.waitingOnRawMaterial')"
            severity="warn"
            icon="mdi mdi-alert"
            v-tooltip.top="t('productionQueue.card.waitingOnRawMaterialTooltip')"
          />
        </div>
        <div v-if="order.note" class="field field-wide">
          <span class="field-label">{{ t('production.lots.detail.record.execution.note') }}</span>
          <span class="field-value field-note">{{ order.note }}</span>
        </div>
      </div>

      <div v-if="assessment" class="assessment">
        <span class="section-label">{{
          t('production.lots.detail.record.execution.assessment')
        }}</span>
        <div class="detail-grid">
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.execution.actualPerPiece')
            }}</span>
            <span class="field-value"
              >{{ formatPieceMinutes(assessment.actual_minutes_per_piece) }} min</span
            >
          </div>
          <div v-if="assessment.actual_setup_minutes !== null" class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.execution.actualSetup')
            }}</span>
            <span class="field-value"
              >{{ formatDecimal(assessment.actual_setup_minutes) }} min</span
            >
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.execution.complexity')
            }}</span>
            <span class="field-value">{{
              t(`productionAssessment.complexity.${assessment.complexity}`)
            }}</span>
          </div>
          <div class="field">
            <span class="field-label">{{
              t('production.lots.detail.record.execution.assessedBy')
            }}</span>
            <span class="field-value"
              >{{ assessment.operator?.full_name ?? getEmptyPlaceholder() }} ({{
                assessment.created
              }})</span
            >
          </div>
          <div v-if="assessment.note" class="field field-wide">
            <span class="field-label">{{ t('production.lots.detail.record.execution.note') }}</span>
            <span class="field-value field-note">{{ assessment.note }}</span>
          </div>
        </div>
      </div>

      <div v-if="order.completions?.length" class="completions">
        <span class="section-label">{{
          t('production.lots.detail.record.execution.orderDialog.completions')
        }}</span>
        <div
          v-for="completion in order.completions ?? []"
          :key="completion.id"
          class="completion-row"
        >
          <i class="mdi mdi-check-bold" aria-hidden="true" />
          <span class="field-value">{{ formatDecimal(completion.quantity) }}</span>
          <span class="field-sublabel">{{ completion.completion_date }}</span>
          <span class="field-sublabel">{{
            completion.operator?.full_name ?? getEmptyPlaceholder()
          }}</span>
          <span v-if="completion.recorded_by_id !== completion.operator_id" class="field-sublabel">
            ({{ t('production.lots.detail.record.execution.recordedBy') }}
            {{ completion.recorded_by?.full_name ?? getEmptyPlaceholder() }})
          </span>
          <span v-if="completion.note" class="field-sublabel">, {{ completion.note }}</span>
        </div>
      </div>

      <LotRecordMeta
        :creator="order.creator"
        :created="order.created.slice(0, 10)"
        :changed="order.changed?.slice(0, 10) ?? null"
        :changed-by="{ user: null, name: null }"
      />
    </div>
  </Dialog>
</template>

<style scoped lang="scss">
.po-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.po-detail-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3) var(--space-5);
}

.field {
  min-width: 0;
}

.field-wide {
  grid-column: 1 / -1;
}

.field-value {
  font-size: var(--font-size-sm);
}

.field-sublabel {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.section-label {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

.assessment,
.completions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--p-content-border-color);
}

.field-note {
  white-space: pre-line;
}

.completion-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
