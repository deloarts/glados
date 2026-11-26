<script setup lang="ts">
// The orders the walk after an Auto-Plan run moved to another day without the
// run placing them: before and after, the shift and why the walk put them
// there. A move within the same day is only counted.
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { TABLE_DEFAULT_ROWS, TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatDateTimeOrDash } from '@/core/utils/dates'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useMadeItemLabel } from '@/features/made-items'
import {
  redatedReasonText,
  redatedShift,
  shiftSeverity,
  type RedatedOrder,
} from '../utils/autoPlanRedated'

const props = defineProps<{
  rows: RedatedOrder[]
  keptDay: number
  walkFailed: boolean
  machineNameById: Record<number, string>
  poolNameById: Record<number, string>
}>()

const { t } = useI18n()
const router = useRouter()
const { format: madeItemLabel } = useMadeItemLabel()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

type Filter = 'all' | 'earlier' | 'later'
const filter = ref<Filter>('all')
const filterOptions = computed(() =>
  (['all', 'earlier', 'later'] as const).map((value) => ({
    value,
    label: t(`productionSchedule.autoPlan.redated.filter.${value}`),
  })),
)

const first = ref(0)
const pageRows = ref(TABLE_DEFAULT_ROWS)

const visibleRows = computed(() =>
  filter.value === 'all'
    ? props.rows
    : props.rows.filter((row) => redatedShift(row).kind === filter.value),
)

function columnLabel(row: RedatedOrder): string {
  switch (row.column) {
    case 'machine':
      return row.machine_id !== null
        ? (props.machineNameById[row.machine_id] ?? `#${row.machine_id}`)
        : ''
    case 'pool':
      return row.machine_pool_id !== null
        ? (props.poolNameById[row.machine_pool_id] ?? `#${row.machine_pool_id}`)
        : ''
    case 'manual':
      return t('productionQueue.board.manualWork')
    case 'inspection':
      return t('productionQueue.board.inspection')
    default:
      return t('productionQueue.board.noMachine')
  }
}

function shiftLabel(row: RedatedOrder): string {
  const shift = redatedShift(row)
  const key = `productionSchedule.autoPlan.redated.shift.${shift.kind}`
  return shift.kind === 'earlier' || shift.kind === 'later'
    ? t(key, { count: shift.days }, shift.days)
    : t(key)
}

function reasonLabel(row: RedatedOrder): { icon: string; label: string; detail: string | null } {
  const text = redatedReasonText(row.reason)
  const plural = typeof text.detailParams.days === 'number' ? text.detailParams.days : undefined
  return {
    icon: text.icon,
    label: t(text.key, text.params),
    detail: text.detailKey
      ? plural === undefined
        ? t(text.detailKey, text.detailParams)
        : t(text.detailKey, text.detailParams, plural)
      : null,
  }
}

function onRowClick(event: { data: RedatedOrder }): void {
  void router.push({ name: 'ProductionOrderDetail', params: { id: event.data.order_id } })
}
</script>

<template>
  <section class="redated" data-testid="autoplan-redated">
    <div class="redated-head">
      <p class="redated-title">{{ t('productionSchedule.autoPlan.redated.title') }}</p>
      <p class="hint">{{ t('productionSchedule.autoPlan.redated.hint') }}</p>
    </div>

    <Message v-if="walkFailed" severity="warn" :closable="false">
      {{ t('productionSchedule.autoPlan.redated.walkFailed') }}
    </Message>

    <template v-else>
      <SelectButton
        v-if="rows.length > 0"
        v-model="filter"
        :options="filterOptions"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        size="small"
        data-testid="autoplan-redated-filter"
      />

      <p v-if="rows.length === 0" class="empty-note">
        {{ t('productionSchedule.autoPlan.redated.none') }}
      </p>
      <DataTable
        v-else
        :value="visibleRows"
        data-key="order_id"
        v-model:first="first"
        v-model:rows="pageRows"
        paginator
        always-show-paginator
        :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
        size="small"
        :show-gridlines="isTableGridlinesEnabled"
        :striped-rows="isTableStripedEnabled"
        row-hover
        class="clickable-rows"
        @row-click="onRowClick"
      >
        <template #empty>
          <EmptyState />
        </template>
        <Column header="#" class="column-fit" body-class="row-number">
          <template #body="{ index }">{{ first + index + 1 }}</template>
        </Column>
        <Column
          field="production_order_number"
          class="column-fit"
          :header="t('productionSchedule.columns.order')"
        />
        <Column field="lot_number" class="column-fit" :header="t('productionSchedule.columns.lot')" />
        <Column class="column-fit" :header="t('productionSchedule.columns.item')">
          <template #body="{ data }: { data: RedatedOrder }">
            {{ madeItemLabel(data.made_item_part_number, data.made_item_revision) }}
          </template>
        </Column>
        <Column class="column-fit" :header="t('productionSchedule.autoPlan.redated.columns.column')">
          <template #body="{ data }: { data: RedatedOrder }">{{ columnLabel(data) }}</template>
        </Column>
        <Column class="column-fit" :header="t('productionSchedule.autoPlan.redated.columns.before')">
          <template #body="{ data }: { data: RedatedOrder }">
            <span class="text-muted before">{{ formatDateTimeOrDash(data.before_planned_start) }}</span>
          </template>
        </Column>
        <Column class="column-fit" :header="t('productionSchedule.autoPlan.redated.columns.after')">
          <template #body="{ data }: { data: RedatedOrder }">
            {{ formatDateTimeOrDash(data.after_planned_start) }}
          </template>
        </Column>
        <Column class="column-fit" :header="t('productionSchedule.autoPlan.redated.columns.shift')">
          <template #body="{ data }: { data: RedatedOrder }">
            <Tag :value="shiftLabel(data)" :severity="shiftSeverity(data, redatedShift(data))" />
          </template>
        </Column>
        <Column :header="t('productionSchedule.autoPlan.redated.columns.reason')">
          <template #body="{ data }: { data: RedatedOrder }">
            <div class="reason">
              <span :class="['mdi', reasonLabel(data).icon]" aria-hidden="true" />
              <div>
                {{ reasonLabel(data).label }}
                <small v-if="reasonLabel(data).detail">{{ reasonLabel(data).detail }}</small>
              </div>
            </div>
          </template>
        </Column>
      </DataTable>

      <p class="kept-note">
        {{ t('productionSchedule.autoPlan.redated.kept', { count: keptDay }, keptDay) }}
      </p>
    </template>
  </section>
</template>

<style scoped lang="scss">
.redated {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.redated-title {
  font-weight: 600;
}

.before {
  text-decoration: line-through;
}

.reason {
  display: flex;
  gap: var(--space-2);
  align-items: flex-start;
  font-size: var(--font-size-sm);

  .mdi {
    color: var(--p-text-muted-color);
  }

  small {
    display: block;
    color: var(--p-text-muted-color);
  }
}

.kept-note {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
