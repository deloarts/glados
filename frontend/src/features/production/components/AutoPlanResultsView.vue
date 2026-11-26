<script setup lang="ts">
// Results step of the Auto-Plan dialog: the before and after placement of
// every moved order, the counts of orders left alone, the orders the
// planner could not place, and the orders the walk after the run re-dated.
import { useI18n } from 'vue-i18n'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useMadeItemLabel } from '@/features/made-items'
import { useAutoPlanTargetLabels } from '../composables/useAutoPlanTargetLabels'
import {
  conflictLabelKey,
  conflictSeverity,
  conflictTooltipKey,
} from '../utils/productionOrderConflicts'
import { skipReasonLabelKey, skipReasonTooltipKey } from '../utils/autoPlanSkipReasons'
import AutoPlanRedatedTable from './AutoPlanRedatedTable.vue'

import type { RedatedOrder } from '../utils/autoPlanRedated'

import type {
  AutoPlanOrderDiffResponse,
  AutoPlanSkippedOrderResponse,
} from '../types/scheduleBoardResponse'

const props = defineProps<{
  results: {
    proposals: AutoPlanOrderDiffResponse[]
    skipped: number
    skippedTodaysPlanned: number
    skippedOrders: AutoPlanSkippedOrderResponse[]
    redated: RedatedOrder[]
    keptDay: number
    walkFailed: boolean
  }
  machineNameById: Record<number, string>
  poolNameById: Record<number, string>
}>()

const { t } = useI18n()
const { format: madeItemLabel } = useMadeItemLabel()
const { machineLabel, poolLabel, formatWindow } = useAutoPlanTargetLabels(
  () => props.machineNameById,
  () => props.poolNameById,
)

// Most rows keep their pool (often none at all), so a pool tag only shows
// when the pool actually changed.
function poolChanged(row: AutoPlanOrderDiffResponse): boolean {
  return row.before_machine_pool_id !== row.after_machine_pool_id
}
</script>

<template>
  <div class="autoplan-results">
    <p v-if="results.proposals.length === 0">{{ t('productionSchedule.autoPlan.noProposals') }}</p>
    <DataTable v-else :value="results.proposals" size="small" data-key="order_id">
      <template #empty>
        <EmptyState />
      </template>
      <Column field="production_order_number" :header="t('productionSchedule.columns.order')" />
      <Column field="lot_number" :header="t('productionSchedule.columns.lot')" />
      <Column :header="t('productionSchedule.columns.item')">
        <template #body="{ data }">
          {{
            madeItemLabel(
              (data as AutoPlanOrderDiffResponse).made_item_part_number,
              (data as AutoPlanOrderDiffResponse).made_item_revision,
            )
          }}
        </template>
      </Column>
      <Column :header="t('productionSchedule.autoPlan.before')">
        <template #body="{ data }">
          <div class="diff-cell">
            <span>{{ machineLabel((data as AutoPlanOrderDiffResponse).before_machine_id) }}</span>
            <Tag
              class="diff-tag"
              v-if="
                poolChanged(data as AutoPlanOrderDiffResponse) &&
                (data as AutoPlanOrderDiffResponse).before_machine_pool_id != null
              "
              :value="
                t('productionQueue.card.poolTag', {
                  pool: poolLabel((data as AutoPlanOrderDiffResponse).before_machine_pool_id!),
                })
              "
              severity="info"
              icon="mdi mdi-view-grid-outline"
            />
            <span class="text-muted">
              {{
                formatWindow(
                  (data as AutoPlanOrderDiffResponse).before_planned_start,
                  (data as AutoPlanOrderDiffResponse).before_planned_end,
                )
              }}
            </span>
          </div>
        </template>
      </Column>
      <Column :header="t('productionSchedule.autoPlan.after')">
        <template #body="{ data }">
          <div class="diff-cell">
            <span>{{ machineLabel((data as AutoPlanOrderDiffResponse).after_machine_id) }}</span>
            <Tag
              class="diff-tag"
              v-if="
                poolChanged(data as AutoPlanOrderDiffResponse) &&
                (data as AutoPlanOrderDiffResponse).after_machine_pool_id != null
              "
              :value="
                t('productionQueue.card.poolTag', {
                  pool: poolLabel((data as AutoPlanOrderDiffResponse).after_machine_pool_id!),
                })
              "
              severity="info"
              icon="mdi mdi-view-grid-outline"
            />
            <span class="text-muted">
              {{
                formatWindow(
                  (data as AutoPlanOrderDiffResponse).after_planned_start,
                  (data as AutoPlanOrderDiffResponse).after_planned_end,
                )
              }}
            </span>
          </div>
        </template>
      </Column>
      <Column :header="t('productionSchedule.columns.conflicts')">
        <template #body="{ data }">
          <div class="conflict-tags">
            <Tag
              v-for="conflict in (data as AutoPlanOrderDiffResponse).conflicts ?? []"
              :key="conflict"
              :value="t(conflictLabelKey(conflict))"
              :severity="conflictSeverity[conflict]"
              icon="mdi mdi-alert"
              v-tooltip.top="t(conflictTooltipKey(conflict))"
            />
            <span
              v-if="((data as AutoPlanOrderDiffResponse).conflicts?.length ?? 0) === 0"
              class="text-muted"
              >{{ getEmptyPlaceholder() }}</span
            >
          </div>
        </template>
      </Column>
    </DataTable>

    <p class="skipped-note">
      {{ t('productionSchedule.autoPlan.skipped', { count: results.skipped }) }}
    </p>
    <p v-if="results.skippedTodaysPlanned > 0" class="skipped-note">
      {{
        t('productionSchedule.autoPlan.skippedTodaysPlanned', {
          count: results.skippedTodaysPlanned,
        })
      }}
    </p>

    <div v-if="results.skippedOrders.length > 0" class="skipped-orders">
      <p class="skipped-orders-title">
        {{
          t('productionSchedule.autoPlan.skippedOrders.title', {
            count: results.skippedOrders.length,
          })
        }}
      </p>
      <ul class="skipped-orders-list">
        <li v-for="row in results.skippedOrders" :key="row.order_id" class="skipped-order-row">
          <span class="skipped-order-number">{{ row.production_order_number }}</span>
          <span class="skipped-order-reason" v-tooltip.top="t(skipReasonTooltipKey(row.reason))">{{
            t(skipReasonLabelKey(row.reason))
          }}</span>
        </li>
      </ul>
    </div>

    <AutoPlanRedatedTable
      :rows="results.redated"
      :kept-day="results.keptDay"
      :walk-failed="results.walkFailed"
      :machine-name-by-id="machineNameById"
      :pool-name-by-id="poolNameById"
    />
  </div>
</template>

<style scoped lang="scss">
.autoplan-results {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.diff-cell {
  display: flex;
  flex-direction: column;
  font-size: var(--font-size-sm);
}

// The column flex stretches children; the pool Tag has a background, so it
// is pinned to its own content width.
.diff-tag {
  align-self: flex-start;
}

.conflict-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.skipped-note {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.skipped-orders-title {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.skipped-orders-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin: 0;
  padding: 0;
  list-style: none;
}

.skipped-order-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}

.skipped-order-number {
  font-weight: 500;
}

.skipped-order-reason {
  color: var(--p-text-muted-color);
}
</style>
