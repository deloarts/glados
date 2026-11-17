<script setup lang="ts">
import { computed, ref } from 'vue'
import { FilterMatchMode } from '@openvue/core/api'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { MadeItemDetailDialog } from '@/features/made-items'
import { MadeItemThumbnailCell } from '@/features/made-items'
import { useMadeItemDetail } from '@/features/made-items'
import { useMadeItemLabel } from '@/features/made-items'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { aggregateBomRows, compareBy, type BomRowBase } from '../utils/bomAggregation'
import type { MadeItemDemandResponse } from '@/features/made-items'
import { DEMAND_STATUSES, DEMAND_STATUS_SEVERITY } from '@/core/utils/demandStatus'
import { formatUnit } from '@/shared/utils/units'
import LabelTag from '@/shared/components/labels/LabelTag.vue'
import type { LocalizedText } from '@/shared/utils/localizedText'

interface MadeBomRow extends BomRowBase {
  itemId: number
  articleName: string
  partNumber: string
  revision: string
  material: string
  articleGroups: { name: LocalizedText | string; label_color: string; label_font_color: string }[]
  unit: string
}

const props = defineProps<{
  demands: MadeItemDemandResponse[]
  /** One row per item and project, with a Project column, for a bill over several projects. */
  byProject?: boolean
}>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const hostStore = useHostStore()

const madeItemDetail = useMadeItemDetail()
const { format: madeItemLabel } = useMadeItemLabel()

// Sorted by part number: a made item has no manufacturer to lead with, the
// way the bought and source bills do.
const bomItems = computed<MadeBomRow[]>(() =>
  aggregateBomRows<MadeItemDemandResponse, MadeBomRow>(props.demands, {
    key: (d) => String(d.made_item_id),
    seed: (d, key) => ({
      key,
      itemId: d.made_item_id,
      articleName: d.item_article_name,
      partNumber: madeItemLabel(d.item_part_number, d.item_revision),
      revision: d.item?.revision ?? getEmptyPlaceholder(),
      material: d.item?.material || getEmptyPlaceholder(),
      articleGroups: d.item?.article_groups ?? [],
      unit: formatUnit(d.unit),
    }),
    quantity: (d) => d.quantity,
    status: (d) => d.status,
    project: props.byProject ? (d) => ({ id: d.project_id, number: d.project_number }) : undefined,
    compare: compareBy(
      (r) => r.partNumber,
      (r) => r.articleName,
    ),
  }),
)

const bomFilters = ref({
  projectNumber: { value: null, matchMode: FilterMatchMode.CONTAINS },
  partNumber: { value: null, matchMode: FilterMatchMode.CONTAINS },
  articleName: { value: null, matchMode: FilterMatchMode.CONTAINS },
  revision: { value: null, matchMode: FilterMatchMode.CONTAINS },
  material: { value: null, matchMode: FilterMatchMode.CONTAINS },
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
      <EmptyState :message="t('resources.projects.detail.bom.emptyMade')" />
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
      <template #body="{ data }: { data: MadeBomRow }">
        <MadeItemThumbnailCell :item-id="data.itemId" :item-name="data.articleName" />
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
      field="partNumber"
      :header="t('resources.projects.detail.bom.columns.partNumber')"
      style="width: 12rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: MadeBomRow }">
        <span
          class="item-link"
          role="button"
          tabindex="0"
          @click.stop="madeItemDetail.openDetailById(data.itemId)"
          @keydown.enter="madeItemDetail.openDetailById(data.itemId)"
          >{{ data.partNumber }}</span
        >
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :aria-label="t('common.filterBy', { column: t('resources.projects.detail.bom.columns.partNumber') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      field="revision"
      :header="t('resources.projects.detail.bom.columns.revision')"
      style="width: 7rem"
      :show-filter-menu="false"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :aria-label="t('common.filterBy', { column: t('resources.projects.detail.bom.columns.revision') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      field="articleName"
      :header="t('resources.projects.itemsDialog.articleName')"
      :show-filter-menu="false"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :aria-label="t('common.filterBy', { column: t('resources.projects.itemsDialog.articleName') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      field="material"
      :header="t('resources.projects.detail.bom.columns.material')"
      style="width: 12rem"
      :show-filter-menu="false"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :aria-label="t('common.filterBy', { column: t('resources.projects.detail.bom.columns.material') })"
          size="small"
          fluid
        />
      </template>
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
      :header="t('resources.projects.itemsDialog.articleGroups')"
      style="width: 14rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: MadeBomRow }">
        <div v-if="data.articleGroups.length" class="article-group-tags">
          <LabelTag
            v-for="(ag, index) in data.articleGroups"
            :key="index"
            :label="ag"
          />
        </div>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter />
    </Column>
    <Column
      :header="t('resources.projects.detail.bom.statusHeader')"
      style="width: 22rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: MadeBomRow }">
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

  <MadeItemDetailDialog
    v-model:visible="madeItemDetail.showDetail.value"
    :item="madeItemDetail.detailItem.value"
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

.article-group-tags {
  display: flex;
  gap: var(--space-1);
  flex-wrap: nowrap;
}
</style>
