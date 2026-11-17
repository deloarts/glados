<script setup lang="ts">
import { computed, ref } from 'vue'
import { FilterMatchMode } from '@openvue/core/api'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import {
  itemKind,
  itemLabel,
  itemManufacturer,
  itemOrderCode1,
  itemOrderCode2,
  itemSublabel,
} from '@/features/source-items'
import { BoughtItemDetailDialog } from '@/features/bought-items'
import { BoughtItemThumbnailCell } from '@/features/bought-items'
import { SourceItemDetailDialog } from '@/features/source-items'
import { SourceItemThumbnailCell } from '@/features/source-items'
import { useBoughtItemDetail } from '@/features/bought-items'
import { useSourceItemDetail } from '@/features/source-items'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { aggregateBomRows, compareBy, type BomRowBase } from '../utils/bomAggregation'
import type { SourceItemDemandResponse } from '@/features/source-items'
import { DEMAND_STATUSES, DEMAND_STATUS_SEVERITY } from '@/core/utils/demandStatus'
import { useErrorToast } from '@/core/composables/useErrorToast'

interface SourceBomRow extends BomRowBase {
  /** Which item the demand points at, for the detail dialog and thumbnail. */
  kind: 'bought' | 'source' | 'none'
  itemId: number | null
  /** Source rows only; drives the thumbnail's shape placeholder. */
  dimension: string | null
  label: string
  sublabel: string
  orderCode1: string
  orderCode2: string
  manufacturerName: string
  unit: string
}

const props = defineProps<{
  demands: SourceItemDemandResponse[]
  /** One row per item and project, with a Project column, for a bill over several projects. */
  byProject?: boolean
}>()

const { t } = useI18n()
const { toastOnError } = useErrorToast()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const hostStore = useHostStore()

const boughtItemDetail = useBoughtItemDetail()
const sourceItemDetail = useSourceItemDetail()

const bomItems = computed<SourceBomRow[]>(() =>
  aggregateBomRows<SourceItemDemandResponse, SourceBomRow>(props.demands, {
    // The key is prefixed by side, since the id spaces overlap. A demand without
    // either keeps its own row.
    key: (d) =>
      d.bought_item_id != null
        ? `b:${d.bought_item_id}`
        : d.source_item_id != null
          ? `s:${d.source_item_id}`
          : `d:${d.id}`,
    seed: (d, key) => ({
      key,
      kind: itemKind(d),
      itemId: d.bought_item_id ?? d.source_item_id,
      dimension: d.source_item?.dimension ?? null,
      label: itemLabel(d),
      sublabel: itemSublabel(d),
      orderCode1: itemOrderCode1(d),
      orderCode2: itemOrderCode2(d),
      manufacturerName: itemManufacturer(d),
      unit: d.unit,
    }),
    quantity: (d) => d.quantity,
    status: (d) => d.status,
    project: props.byProject ? (d) => ({ id: d.project_id, number: d.project_number }) : undefined,
    // Ordered by manufacturer so an item's suppliers stay together.
    compare: compareBy(
      (r) => r.manufacturerName,
      (r) => r.label,
    ),
  }),
)

function openDetail(row: SourceBomRow): void {
  if (row.itemId == null) return
  if (row.kind === 'bought') boughtItemDetail.openDetailById(row.itemId).catch(toastOnError())
  else if (row.kind === 'source') sourceItemDetail.openDetailById(row.itemId).catch(toastOnError())
}

const bomFilters = ref({
  projectNumber: { value: null, matchMode: FilterMatchMode.CONTAINS },
  label: { value: null, matchMode: FilterMatchMode.CONTAINS },
  sublabel: { value: null, matchMode: FilterMatchMode.CONTAINS },
  orderCode1: { value: null, matchMode: FilterMatchMode.CONTAINS },
  orderCode2: { value: null, matchMode: FilterMatchMode.CONTAINS },
  manufacturerName: { value: null, matchMode: FilterMatchMode.CONTAINS },
  unit: { value: null, matchMode: FilterMatchMode.CONTAINS },
})
</script>

<template>
  <DataTable
    :value="bomItems"
    v-model:filters="bomFilters"
    filter-display="row"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    scrollable
    scroll-height="flex"
    table-style="width: auto"
    resizable-columns
    column-resize-mode="expand"
  >
    <template #empty>
      <EmptyState :message="t('resources.projects.detail.bom.emptySource')" />
    </template>
    <Column header="#" style="width: 3rem" body-class="row-number" :show-filter-menu="false">
      <template #body="{ index }">{{ index + 1 }}</template>
      <template #filter />
    </Column>
    <Column
      v-if="hostStore.storageEnabled"
      :header="t('resources.projects.detail.bom.columns.image')"
      style="width: 3.25rem; min-width: 3.25rem; padding: var(--space-1) var(--space-2)"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: SourceBomRow }">
        <BoughtItemThumbnailCell
          v-if="data.kind === 'bought' && data.itemId !== null"
          :item-id="data.itemId"
          :item-name="data.label"
        />
        <SourceItemThumbnailCell
          v-else-if="data.kind === 'source' && data.itemId !== null"
          :item-id="data.itemId"
          :item-name="data.label"
          :dimension="data.dimension"
        />
      </template>
      <template #filter />
    </Column>
    <Column
      v-if="byProject"
      field="projectNumber"
      :header="t('resources.projects.detail.bom.columns.project')"
      :show-filter-menu="false"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :aria-label="t('common.filterBy', { column: t('resources.projects.detail.bom.columns.project') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      field="label"
      :header="t('resources.projects.detail.bom.columns.item')"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: SourceBomRow }">
        <span
          v-if="data.itemId !== null"
          class="item-link"
          role="button"
          tabindex="0"
          @click.stop="openDetail(data)"
          @keydown.enter="openDetail(data)"
          >{{ data.label }}</span
        >
        <span v-else>{{ data.label }}</span>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :aria-label="t('common.filterBy', { column: t('resources.projects.detail.bom.columns.item') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      field="sublabel"
      :header="t('resources.projects.detail.bom.columns.detail')"
      style="width: 16rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: SourceBomRow }">{{
        data.sublabel || getEmptyPlaceholder()
      }}</template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :aria-label="t('common.filterBy', { column: t('resources.projects.detail.bom.columns.detail') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      field="orderCode1"
      :header="t('resources.projects.itemsDialog.orderCode')"
      style="width: 12rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: SourceBomRow }">{{
        data.orderCode1 || getEmptyPlaceholder()
      }}</template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :aria-label="t('common.filterBy', { column: t('resources.projects.itemsDialog.orderCode') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      field="orderCode2"
      :header="t('resources.projects.itemsDialog.orderCode2')"
      style="width: 12rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: SourceBomRow }">{{
        data.orderCode2 || getEmptyPlaceholder()
      }}</template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :aria-label="t('common.filterBy', { column: t('resources.projects.itemsDialog.orderCode2') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      field="manufacturerName"
      :header="t('resources.projects.itemsDialog.manufacturer')"
      :show-filter-menu="false"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :aria-label="t('common.filterBy', { column: t('resources.projects.itemsDialog.manufacturer') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      :header="t('resources.projects.detail.bom.columns.kind')"
      style="width: 8rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: SourceBomRow }">
        <Tag
          v-if="data.kind !== 'none'"
          :value="t('resources.projects.detail.bom.kind.' + data.kind)"
          :severity="data.kind === 'bought' ? 'info' : 'secondary'"
          size="small"
        />
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter />
    </Column>
    <Column
      field="unit"
      :header="t('resources.projects.itemsDialog.unit')"
      style="width: 6rem"
      :show-filter-menu="false"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :aria-label="t('common.filterBy', { column: t('resources.projects.itemsDialog.unit') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      field="qtyDemanded"
      :header="t('resources.projects.itemsDialog.qtyDemanded')"
      style="width: 9rem"
      :show-filter-menu="false"
    >
      <template #filter />
    </Column>
    <Column
      field="qtyFulfilled"
      :header="t('resources.projects.itemsDialog.qtyFulfilled')"
      style="width: 9rem"
      :show-filter-menu="false"
    >
      <template #filter />
    </Column>
    <Column
      :header="t('resources.projects.detail.bom.statusHeader')"
      style="width: 22rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: SourceBomRow }">
        <div class="status-tags">
          <Tag
            v-for="status in DEMAND_STATUSES.filter(
              (s) => (data.statusCounts[s] ?? 0) > 0,
            )"
            :key="status"
            :value="`${data.statusCounts[status] ?? 0} ${t('resources.projects.detail.bom.status.' + status)}`"
            :severity="DEMAND_STATUS_SEVERITY[status]"
            size="small"
          />
        </div>
      </template>
      <template #filter />
    </Column>
    <Column style="width: 100%"></Column>
  </DataTable>

  <BoughtItemDetailDialog
    v-model:visible="boughtItemDetail.showDetail.value"
    :item="boughtItemDetail.detailItem.value"
  />
  <SourceItemDetailDialog
    v-model:visible="sourceItemDetail.showDetail.value"
    :item="sourceItemDetail.detailItem.value"
  />
</template>

<style scoped lang="scss">
.item-link {
  cursor: pointer;
  color: inherit;
  width: fit-content;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.status-tags {
  display: flex;
  gap: var(--space-1);
  flex-wrap: nowrap;
}
</style>
