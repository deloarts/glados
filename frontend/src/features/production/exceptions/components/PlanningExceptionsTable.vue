<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { TABLE_DEFAULT_ROWS, TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatISODate, formatISODateTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import {
  BoughtItemDetailDialog,
  BoughtItemThumbnailCell,
  useBoughtItemDetail,
} from '@/features/bought-items'
import { MadeItemDetailDialog, MadeItemThumbnailCell, useMadeItemDetail } from '@/features/made-items'
import {
  SourceItemDetailDialog,
  SourceItemThumbnailCell,
  useSourceItemDetail,
} from '@/features/source-items'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import EmptyState from '@/shared/components/EmptyState.vue'
import { formatUnit } from '@/shared/utils/units'

import PlanningExceptionItemCell from './PlanningExceptionItemCell.vue'
import { PLANNING_EXCEPTION_SEVERITY } from '../utils/planningExceptionKinds'

import type {
  PlanningExceptionKind,
  PlanningExceptionResponse,
} from '../types/planningExceptionResponse'

defineProps<{
  rows: PlanningExceptionResponse[]
}>()

const { t } = useI18n()
const { toastOnError } = useErrorToast()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const hostStore = useHostStore()
const { openLotDetail } = useLotDetail()
const madeItemDetail = useMadeItemDetail()
const boughtItemDetail = useBoughtItemDetail()
const sourceItemDetail = useSourceItemDetail()

// The index a cell gets counts within the page, so the row number adds the
// rows of the pages before it.
const first = ref(0)
const pageRows = ref(TABLE_DEFAULT_ROWS)

function rowKey(row: PlanningExceptionResponse): string {
  return [row.kind, row.family, row.demand_id, row.lot_id, row.order_id].join(':')
}

function openItem(row: PlanningExceptionResponse): void {
  if (row.item_id === null) return
  const detail =
    row.item_kind === 'made'
      ? madeItemDetail
      : row.item_kind === 'bought'
        ? boughtItemDetail
        : sourceItemDetail
  detail.openDetailById(row.item_id).catch(toastOnError())
}

// What the planner needs to know about the row, in one sentence per kind.
function detail(row: PlanningExceptionResponse): string {
  const unit = formatUnit(row.unit)
  switch (row.kind) {
    case 'lost_at_receipt':
    case 'closed_short':
    case 'lot_ended_short':
      return t(`productionExceptions.detail.${row.kind}`, {
        quantity: row.quantity_short ?? 0,
        unit,
        demand: row.demand_id ?? '',
      })
    case 'material_short':
      if (row.unallocated && row.unallocated > 0) {
        return t('productionExceptions.detail.material_unallocated', {
          quantity: row.unallocated,
          unit,
        })
      }
      return t('productionExceptions.detail.material_undated')
    case 'late':
      return row.planned_end
        ? t('productionExceptions.detail.late_planned', {
            target: formatISODate(row.target_date ?? ''),
            end: formatISODate(row.planned_end),
          })
        : t('productionExceptions.detail.late_passed', {
            target: formatISODate(row.target_date ?? ''),
          })
  }
  return ''
}

function lineLabel(row: PlanningExceptionResponse): string | null {
  if (!row.order_number) return null
  return t('productionExceptions.line', { order: row.order_number, position: row.line_position })
}
</script>

<template>
  <DataTable
    class="exceptions-table"
    v-model:first="first"
    v-model:rows="pageRows"
    :value="rows"
    :data-key="rowKey"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    paginator
    always-show-paginator
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    size="small"
    scrollable
    scroll-height="flex"
  >
    <template #empty>
      <EmptyState icon="mdi mdi-check-circle-outline" :message="t('productionExceptions.empty')" />
    </template>

    <Column :header="t('productionExceptions.columns.rowNumber')" class="column-fit" body-class="row-number">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>

    <Column :header="t('productionExceptions.columns.kind')" class="column-fit">
      <template #body="{ data }">
        <Tag
          :value="t(`productionExceptions.kind.${data.kind}`)"
          :severity="PLANNING_EXCEPTION_SEVERITY[data.kind as PlanningExceptionKind]"
        />
      </template>
    </Column>

    <Column :header="t('productionExceptions.columns.project')" class="column-fit">
      <template #body="{ data }">
        <div v-if="data.project_number" class="stack">
          <RouterLink
            v-if="data.project_id !== null"
            class="link link--strong"
            :to="`/workspace/projects/${data.project_id}`"
            >{{ data.project_number }}</RouterLink
          >
          <span v-else class="strong">{{ data.project_number }}</span>
          <span v-if="data.project_customer" class="muted">{{ data.project_customer }}</span>
        </div>
        <span v-else class="muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>

    <Column v-if="hostStore.storageEnabled" class="column-fit thumbnail-column">
      <template #body="{ data }">
        <MadeItemThumbnailCell
          v-if="data.item_kind === 'made' && data.item_id !== null"
          :item-id="data.item_id"
          :item-name="data.item_name"
        />
        <BoughtItemThumbnailCell
          v-else-if="data.item_kind === 'bought' && data.item_id !== null"
          :item-id="data.item_id"
          :item-name="data.item_name"
        />
        <SourceItemThumbnailCell
          v-else-if="data.item_kind === 'source' && data.item_id !== null"
          :item-id="data.item_id"
          :item-name="data.item_name"
          :dimension="data.item_number"
        />
      </template>
    </Column>

    <Column :header="t('productionExceptions.columns.item')" class="column-fit">
      <template #body="{ data }">
        <PlanningExceptionItemCell :row="data" @open="openItem" />
      </template>
    </Column>

    <Column :header="t('productionExceptions.columns.subject')" class="column-fit">
      <template #body="{ data }">
        <div class="stack">
          <a
            v-if="data.lot_id"
            href="#"
            class="link"
            @click.prevent="openLotDetail(data.lot_id)"
            >{{ data.lot_number }}</a
          >
          <RouterLink
            v-if="data.order_id"
            class="link"
            :to="{ name: 'OrderDetail', params: { id: data.order_id } }"
            >{{ lineLabel(data) }}</RouterLink
          >
          <span v-if="data.demand_id && data.family" class="muted">{{
            t(`productionExceptions.family.${data.family}`, { id: data.demand_id })
          }}</span>
        </div>
      </template>
    </Column>

    <Column :header="t('productionExceptions.columns.detail')" class="column-fit">
      <template #body="{ data }">{{ detail(data) }}</template>
    </Column>

    <Column :header="t('productionExceptions.columns.since')" class="column-fit">
      <template #body="{ data }">{{
        data.since ? formatISODateTime(data.since) : getEmptyPlaceholder()
      }}</template>
    </Column>

    <!-- Takes the width the content-wide columns leave, so the table spans
         its card without stretching them. -->
    <Column />
  </DataTable>

  <MadeItemDetailDialog
    v-model:visible="madeItemDetail.showDetail.value"
    :item="madeItemDetail.detailItem.value"
  />
  <BoughtItemDetailDialog
    v-model:visible="boughtItemDetail.showDetail.value"
    :item="boughtItemDetail.detailItem.value"
  />
  <SourceItemDetailDialog
    v-model:visible="sourceItemDetail.showDetail.value"
    :item="sourceItemDetail.detailItem.value"
  />
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

/* Links read as text and show their colour only under the pointer. */
.link {
  color: inherit;
  text-decoration: none;
  width: fit-content;
}

.link:hover {
  color: var(--p-primary-color);
  text-decoration: underline;
}

.link--strong,
.strong {
  font-weight: 600;
}

.muted {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
}

/* The columns are only as wide as their content, so a little more room on
   either side keeps them from reading as one block. */
.exceptions-table :deep(th),
.exceptions-table :deep(td) {
  padding-inline: var(--space-3);
}

.exceptions-table :deep(td.thumbnail-column) {
  padding: var(--space-1) var(--space-2);
}
</style>
