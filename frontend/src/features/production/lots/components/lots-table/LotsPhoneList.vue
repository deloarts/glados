<script setup lang="ts">
/**
 * The lots list on a phone: the row number, the item's picture, the lot and
 * its item, the status and the required delivery date, nothing else. The desktop table's steps,
 * sources, filters, bulk selection and context menu stay on the desktop.
 * Tapping a row opens the lot.
 */
import { useI18n } from 'vue-i18n'

import { formatDateOrDash } from '@/core/utils/dates'
import { useHostStore } from '@/core/host/stores/hostStore'
import { MadeItemThumbnailCell, useMadeItemLabel } from '@/features/made-items'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useProductionLotsStore } from '../../../stores/productionLotsStore'
import { lotStatusSeverity } from '../../../utils/lotStatus'

import type { DataTablePageEvent, DataTableRowSelectEvent } from 'openvue/datatable'
import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

defineProps<{
  first: number
  rows: number
}>()

const emit = defineEmits<{
  page: [event: DataTablePageEvent]
  'open-lot': [lot: LotSummaryResponse]
}>()

const { t } = useI18n()
const { format: madeItemLabel } = useMadeItemLabel()
const lotsStore = useProductionLotsStore()
const hostStore = useHostStore()

function onRowSelect(event: DataTableRowSelectEvent<LotSummaryResponse>): void {
  emit('open-lot', event.data)
}
</script>

<template>
  <DataTable
    :value="lotsStore.items"
    data-key="id"
    selection-mode="single"
    lazy
    paginator
    paginator-template="PrevPageLink CurrentPageReport NextPageLink"
    current-page-report-template="{first}–{last} / {totalRecords}"
    :total-records="lotsStore.total"
    :first="first"
    :rows="rows"
    scrollable
    scroll-height="flex"
    size="small"
    class="clickable-rows fixed-layout-table lots-phone-list"
    data-testid="lots-phone-list"
    @page="emit('page', $event)"
    @row-select="onRowSelect"
  >
    <Column
      :header="t('production.lots.columns.rowNumber')"
      style="width: 2.5rem"
      body-class="row-number"
    >
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>
    <Column
      v-if="hostStore.storageEnabled"
      style="width: 3.25rem; padding: var(--space-1) var(--space-2)"
    >
      <template #body="{ data }">
        <MadeItemThumbnailCell
          :item-id="data.made_item_id"
          :item-name="data.made_item_article_name"
        />
      </template>
    </Column>
    <Column :header="t('production.lots.columns.lotNumber')">
      <template #body="{ data }">
        <div class="lot-cell">
          <span class="lot-number">{{ data.lot_number }}</span>
          <span class="lot-item">{{
            data.made_item_part_number
              ? madeItemLabel(data.made_item_part_number, data.made_item_revision)
              : t('production.lots.noPartNumber')
          }}</span>
          <span class="lot-article">{{ data.made_item_article_name }}</span>
        </div>
      </template>
    </Column>
    <Column :header="t('production.lots.columns.status')" style="width: 8rem">
      <template #body="{ data }">
        <Tag
          :value="t(`production.lots.status.${data.status}`)"
          :severity="lotStatusSeverity[data.status as LotSummaryResponse['status']]"
        />
      </template>
    </Column>
    <Column :header="t('production.lots.columns.requiredDeliveryDate')" style="width: 6.5rem">
      <template #body="{ data }">
        {{ formatDateOrDash(data.target_date) }}
      </template>
    </Column>

    <template #empty>
      <EmptyState />
    </template>
  </DataTable>
</template>

<style scoped lang="scss">
// Fixed layout: the lot column takes what the status and the date leave, so
// a long article name ends in an ellipsis instead of widening the table.
.lots-phone-list {
  --table-min-width: 0;
}

.lot-cell {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.lot-number {
  font-weight: 600;
}

.lot-item,
.lot-article {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: var(--font-size-sm);
}

.lot-article {
  color: var(--p-text-muted-color);
}
</style>
