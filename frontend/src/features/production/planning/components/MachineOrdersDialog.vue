<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { formatDateOrDash } from '@/core/utils/dates'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { MadeItemThumbnailCell, useMadeItemLabel } from '@/features/made-items'
import EmptyState from '@/shared/components/EmptyState.vue'
import {
  conflictLabelKey,
  conflictSeverity,
  conflictTooltipKey,
} from '../../utils/productionOrderConflicts'

import type { ScheduleBoardOrderResponse } from '../../types/scheduleBoardResponse'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

interface Props {
  machineName: string
  orders: ScheduleBoardOrderResponse[]
  /**
   * Machine names by id, so a floating order's trial machine can show as
   * reserved. Missing entries fall back to the generic tooltip.
   */
  machineNamesById?: Record<number, string>
}

const props = defineProps<Props>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const { format: madeItemLabel } = useMadeItemLabel()

function floatingTooltip(order: ScheduleBoardOrderResponse): string {
  const machine =
    order.trial_machine_id != null ? props.machineNamesById?.[order.trial_machine_id] : undefined
  return machine
    ? t('productionSchedule.floatingTooltipReserved', { machine })
    : t('productionSchedule.floatingTooltip')
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :header="machineName" :style="{ width: 'var(--dialog-width-full)' }">
    <DataTable
      :value="orders"
      size="small"
      data-key="order_id"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
    >
      <Column header="#" style="width: 3rem" body-class="row-number">
        <template #body="{ index }">{{ index + 1 }}</template>
      </Column>
      <Column field="production_order_number" :header="t('productionSchedule.columns.order')" />
      <Column field="lot_number" :header="t('productionSchedule.columns.lot')" />
      <Column field="project_number" :header="t('productionSchedule.columns.project')" />
      <Column :header="t('productionSchedule.columns.item')">
        <template #body="{ data }">
          <div class="item-cell">
            <MadeItemThumbnailCell
              :item-id="(data as ScheduleBoardOrderResponse).made_item_id"
              :item-name="(data as ScheduleBoardOrderResponse).made_item_part_number"
              size="2rem"
            />
            {{
              madeItemLabel(
                (data as ScheduleBoardOrderResponse).made_item_part_number,
                (data as ScheduleBoardOrderResponse).made_item_revision,
              )
            }}
          </div>
        </template>
      </Column>
      <Column :header="t('productionSchedule.columns.step')">
        <template #body="{ data }">
          {{ (data as ScheduleBoardOrderResponse).lot_position_sequence }}/{{
            (data as ScheduleBoardOrderResponse).lot_position_count
          }}
        </template>
      </Column>
      <Column :header="t('productionSchedule.columns.window')">
        <template #body="{ data }">
          <span class="window-cell">
            {{ formatDateOrDash((data as ScheduleBoardOrderResponse).planned_start) }} –
            {{ formatDateOrDash((data as ScheduleBoardOrderResponse).planned_end) }}
            <Tag
              v-if="(data as ScheduleBoardOrderResponse).is_floating"
              :value="t('productionSchedule.floatingTag')"
              severity="info"
              icon="mdi mdi-help-circle-outline"
              v-tooltip.top="floatingTooltip(data as ScheduleBoardOrderResponse)"
            />
          </span>
        </template>
      </Column>
      <Column :header="t('productionSchedule.columns.conflicts')">
        <template #body="{ data }">
          <div class="conflict-tags">
            <Tag
              v-for="conflict in (data as ScheduleBoardOrderResponse).conflicts ?? []"
              :key="conflict"
              :value="t(conflictLabelKey(conflict))"
              :severity="conflictSeverity[conflict]"
              icon="mdi mdi-alert"
              v-tooltip.top="t(conflictTooltipKey(conflict))"
            />
            <span
              v-if="((data as ScheduleBoardOrderResponse).conflicts?.length ?? 0) === 0"
              class="text-muted"
              >{{ getEmptyPlaceholder() }}</span
            >
          </div>
        </template>
      </Column>
      <template #empty>
        <EmptyState :message="t('productionSchedule.machineOrdersEmpty')" />
      </template>
    </DataTable>

    <template #footer>
      <Button :label="t('common.close')" severity="secondary" @click="visible = false" />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.item-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.window-cell {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.conflict-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
</style>
