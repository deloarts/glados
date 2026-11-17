<script setup lang="ts">
// Server-paged made items catalogue table with column filters, optional
// grouping by article group, bulk selection in edit mode and the row
// context menu.
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import {
  TABLE_ROWS_PER_PAGE_OPTIONS,
  TABLE_COL_WIDTH_ID,
  TABLE_COL_WIDTH_STATUS,
  TABLE_COL_WIDTH_REVISION,
} from '@/core/constants/table'
import { useServerTable } from '@/core/composables/useServerTable'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import { useArticleGroupsStore } from '@/features/article-groups'
import { SourceItemDetailDialog } from '@/features/source-items'
import { BoughtItemDetailDialog } from '@/features/bought-items'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useCatalogueRowSelection } from '@/shared/composables/useCatalogueRowSelection'
import { useDialogTarget } from '@/shared/composables/useDialogTarget'
import { useKeyedDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { useKeyedFilterMetaModel } from '@/shared/composables/useFilterMetaModel'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'

import { getMadeItemFileBlob } from '../api/madeItemFilesApi'
import { useMadeItemsStore } from '../stores/madeItemsStore'
import { useMadeItemsCatalogueEditStore } from '../stores/madeItemsCatalogueEditStore'
import { useMadeItemsChangelogStore } from '../stores/madeItemsChangelogStore'
import { useMadeItemsCatalogueFiltersStore } from '../stores/madeItemsCatalogueFiltersStore'
import {
  useMadeItemsCatalogueViewStore,
  useMadeItemsShowAllRevisionsStore,
} from '../stores/madeItemsCatalogueViewStore'
import {
  MADE_ITEM_DATA_SOURCE_OPTIONS,
  MADE_ITEM_STATUS_OPTIONS,
  useMadeItemsCatalogueColumnsStore,
} from '../stores/madeItemsCatalogueColumnsStore'
import { useMadeItemsCatalogueActions } from '../composables/useMadeItemsCatalogueActions'
import { useMadeItemsCatalogueQuery } from '../composables/useMadeItemsCatalogueQuery'
import MadeItemDetailDialog from './MadeItemDetailDialog.vue'
import ItemChangelogDialog from '@/shared/components/items/ItemChangelogDialog.vue'
import MadeItemCreateForm from './MadeItemCreateForm.vue'
import MadeItemDemandCreateForm from './MadeItemDemandCreateForm.vue'
import { useMadeItemLotDialogs } from '../composables/useMadeItemLotDialogs'
import MadeItemMergeDialog from './MadeItemMergeDialog.vue'
import MadeItemsCatalogueCell from './MadeItemsCatalogueCell.vue'
import MadeItemSuccessorPopover from './MadeItemSuccessorPopover.vue'

import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MadeItemResponse, MadeItemFile } from '../types/madeItemsResponse'
import type { SourceItemResponse } from '@/features/source-items'
import type { BoughtItemResponse } from '@/features/bought-items'
import { groupRowsByLabel } from '@/core/utils/tableRowGrouping'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const { t } = useI18n()
const router = useRouter()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const statusOptions = computed(() =>
  MADE_ITEM_STATUS_OPTIONS.map((s) => ({
    label: t(`madeItems.catalogue.status.${s}`),
    value: s,
  })),
)
// Shows the labels and filters by the stored value the backend matches.
const dataSourceOptions = computed(() =>
  MADE_ITEM_DATA_SOURCE_OPTIONS.map((source) => ({
    label: t(`madeItems.catalogue.dataSources.${source}`),
    value: source,
  })),
)

const madeItemsStore = useMadeItemsStore()
const hostStore = useHostStore()

watchLoadingBar(() => madeItemsStore.loading)
const columnsStore = useMadeItemsCatalogueColumnsStore()
const editStore = useMadeItemsCatalogueEditStore()
const filtersStore = useMadeItemsCatalogueFiltersStore()
const viewStore = useMadeItemsCatalogueViewStore()
const showAllRevisionsStore = useMadeItemsShowAllRevisionsStore()
const articleGroupsStore = useArticleGroupsStore()
const changelogStore = useMadeItemsChangelogStore()

const {
  canWrite,
  canDelete,
  detailItem,
  showDetail,
  detailEditOnOpen,
  copyFromItem,
  showCopyForm,
  copyItem,
  revisionOfItem,
  showRevisionForm,
  changelogItem,
  showChangelogDialog,
  showChangelogFor,
  mergeSourceItem,
  showMergeDialog,
  mergeItem,
  demandForItem,
  showDemandForm,
  historyItem,
  showHistoryDialog,
  editItem,
  contextMenuItem,
  contextMenuItems,
} = useMadeItemsCatalogueActions()

// The lot history comes from the hosting page.
const lotDialogs = useMadeItemLotDialogs()

const groupedItems = computed(() => {
  const items = madeItemsStore.items
  if (!viewStore.groupBy) return items

  return groupRowsByLabel(
    items,
    '_categoryGroup',
    (item) => localizeLabel(item.article_groups?.[0]?.name) || getEmptyPlaceholder(),
  )
})

const groupRowsBy = computed(() => {
  if (!viewStore.groupBy) return undefined
  return '_categoryGroup'
})

const { isSelectionColumnVisible, tableSelectionProps, onRowClick, onRowSelect, onSelectionUpdate } =
  useCatalogueRowSelection<MadeItemResponse>({
    editStore,
    canSelect: () => canWrite.value,
    openDetail: (item) => navigateToDetail(item),
  })

function navigateToDetail(item: MadeItemResponse): void {
  void router.push(`/catalogue/made-items/${item.id}`)
}

const { filters, dateRangeFilters, search, showArchived, clearTrigger } = storeToRefs(filtersStore)
const { sortBy, sortDir } = storeToRefs(viewStore)
const listQuery = useMadeItemsCatalogueQuery()

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage, onFilter } =
  useServerTable({
    fetchParams: ({ first, rows }) => ({
      skip: first,
      limit: rows,
      ...listQuery(),
    }),
    fetch: (params) => madeItemsStore.refresh(params),
  })

const FIXED_COLUMN_WIDTHS: Record<string, string> = {
  id: TABLE_COL_WIDTH_ID,
  status: TABLE_COL_WIDTH_STATUS,
  revision: TABLE_COL_WIDTH_REVISION,
  image: '3.25rem',
  public_id: '18rem',
  files: '9rem',
}

// Fields whose body is rendered by MadeItemsCatalogueCell instead of the
// plain value.
const CELL_FIELDS = new Set([
  'status',
  'article_groups',
  'successor_item_id',
  'created',
  'changed',
  'image',
  'article_name',
  'source_label',
  'processes',
  'files',
  'public_id',
  'part_number',
  'data_source',
])

/** The image and files columns have nothing to show while file storage is off. */
const renderedColumns = computed(() =>
  columnsStore.visibleColumns.filter(
    (column) => (column.field !== 'image' && column.field !== 'files') || hostStore.storageEnabled,
  ),
)

function columnWidth(field: string): string {
  return FIXED_COLUMN_WIDTHS[field] ?? '10%'
}

const { getDateRangeModel, setDateRangeModel } = useKeyedDateRangeFilter(dateRangeFilters, onFilter)
const { getFilterValue, setFilterValue } = useKeyedFilterMetaModel(filters, onFilter)

watch(search, resetAndFetchDebounced)

watch(showArchived, resetAndFetch)

watch(clearTrigger, resetAndFetch)

watch(
  () => madeItemsStore.refreshTrigger,
  () => fetchItems(),
)

watch([sortBy, sortDir], resetAndFetch)

watch(() => showAllRevisionsStore.showAllRevisions, resetAndFetch)

onMounted(() => {
  if (articleGroupsStore.items.length === 0) {
    void articleGroupsStore.refresh()
  }
})

const {
  target: sourceItemDetail,
  visible: showSourceItemDetail,
  open: openSourceItemDetail,
} = useDialogTarget<SourceItemResponse>()
const {
  target: boughtItemDetail,
  visible: showBoughtItemDetail,
  open: openBoughtItemDetail,
} = useDialogTarget<BoughtItemResponse>()

interface FilePreviewTarget {
  itemId: number
  file: MadeItemFile
}

const filePreview = ref<FilePreviewTarget | null>(null)
const showFilePreview = ref(false)

function openFilePreview(itemId: number, file: MadeItemFile): void {
  filePreview.value = { itemId, file }
  showFilePreview.value = true
}

function fetchPreviewBlob(): Promise<Blob> {
  const target = filePreview.value
  if (!target) return Promise.reject(new Error('no file selected for preview'))
  return getMadeItemFileBlob(target.itemId, target.file.id)
}

const successorPopover = ref<InstanceType<typeof MadeItemSuccessorPopover>>()

function openSuccessor(event: Event, id: number): void {
  void successorPopover.value?.show(event, id)
}

const cm = ref()

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}
</script>

<template>
  <DataTable
    :value="groupedItems"
    :selection-mode="tableSelectionProps.selectionMode"
    :meta-key-selection="tableSelectionProps.metaKeySelection"
    :selection="tableSelectionProps.selection"
    @update:selection="onSelectionUpdate"
    v-model:context-menu-selection="contextMenuItem"
    @row-contextmenu="onRowContextMenu"
    @row-click="onRowClick"
    @row-select="onRowSelect"
    data-key="id"
    lazy
    paginator
    :total-records="madeItemsStore.total"
    :first="first"
    :rows="rows"
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    @page="onPage"
    table-style="min-width: 50rem"
    scrollable
    scroll-height="flex"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    resizable-columns
    column-resize-mode="expand"
    v-model:filters="filters"
    filter-display="row"
    @filter="onFilter"
    size="small"
    :row-group-mode="viewStore.groupBy ? 'subheader' : undefined"
    :group-rows-by="groupRowsBy"
    class="phone-columns catalogue-rows-clickable mic-catalogue-table"
  >
    <template v-if="viewStore.groupBy" #groupheader="{ data }">
      <div class="group-header">
        <i class="mdi mdi-tag" aria-hidden="true" />
        <span class="group-header-label">{{ data._categoryGroup }}</span>
      </div>
    </template>
    <template #empty>
      <EmptyState />
    </template>
    <Column
      v-if="isSelectionColumnVisible"
      frozen
      selection-mode="multiple"
      header-style="width: 3rem; max-width: 3rem"
    />
    <Column v-if="viewStore.showActions" style="width: 12rem" frozen align-frozen="right">
      <template #body="{ data }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            rounded
            :disabled="!canWrite"
            v-tooltip.focus="t('madeItems.catalogue.controls.edit')"
            :aria-label="t('madeItems.catalogue.controls.edit')"
            @click="editItem(data as MadeItemResponse)"
          />
          <Button
            icon="mdi mdi-content-copy"
            size="small"
            severity="secondary"
            text
            rounded
            :disabled="!canWrite"
            v-tooltip.focus="t('madeItems.catalogue.controls.copy')"
            :aria-label="t('madeItems.catalogue.controls.copy')"
            @click="copyItem(data as MadeItemResponse)"
          />
          <Button
            icon="mdi mdi-source-merge"
            size="small"
            severity="secondary"
            text
            rounded
            :disabled="!canDelete"
            v-tooltip.focus="t('madeItems.catalogue.controls.merge')"
            :aria-label="t('madeItems.catalogue.controls.merge')"
            @click="mergeItem(data as MadeItemResponse)"
          />
          <Button
            icon="mdi mdi-history"
            size="small"
            severity="secondary"
            text
            rounded
            v-tooltip.focus="t('madeItems.catalogue.contextMenu.showChangelog')"
            :aria-label="t('madeItems.catalogue.contextMenu.showChangelog')"
            @click="showChangelogFor(data as MadeItemResponse)"
          />
        </div>
      </template>
    </Column>
    <Column
      frozen
      header="#"
      class="phone-row-number"
      header-style="width: 3rem"
      body-class="row-number"
    >
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>

    <template v-for="column in renderedColumns" :key="column.field">
      <Column
        :field="column.field"
        :header="column.header"
        :class="column.phoneClass"
        :show-filter-menu="false"
        :style="{ width: columnWidth(column.field) }"
      >
        <template v-if="CELL_FIELDS.has(column.field)" #body="{ data }">
          <MadeItemsCatalogueCell
            :item="data as MadeItemResponse"
            :field="column.field"
            @open-bought-item="openBoughtItemDetail"
            @open-source-item="openSourceItemDetail"
            @open-successor="openSuccessor"
            @preview-file="openFilePreview"
          />
        </template>

        <template v-if="column.filter" #filter="{ filterModel, filterCallback }">
          <Select
            v-if="column.filter === 'status'"
            v-model="filterModel.value"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="t('madeItems.catalogue.filters.any')"
            :aria-label="t('common.filterBy', { column: column.header })"
            size="small"
            fluid
            @change="filterCallback()"
            @clear="filterCallback()"
          />
          <Select
            v-else-if="column.filter === 'data-source'"
            v-model="filterModel.value"
            :options="dataSourceOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="t('madeItems.catalogue.filters.any')"
            :aria-label="t('common.filterBy', { column: column.header })"
            size="small"
            fluid
            @change="filterCallback()"
            @clear="filterCallback()"
          />
          <Select
            v-else-if="column.filter === 'article-group'"
            v-model="filterModel.value"
            :options="articleGroupsStore.items"
            :option-label="labelName"
            option-value="id"
            :loading="articleGroupsStore.loading"
            show-clear
            :placeholder="t('madeItems.catalogue.filters.any')"
            :aria-label="t('common.filterBy', { column: column.header })"
            size="small"
            fluid
            @change="filterCallback()"
            @clear="filterCallback()"
          />
          <UserDateFilter
            v-else-if="column.filter === 'date-range' && column.userFilterParam"
            :user-id="getFilterValue<number>(column.userFilterParam)"
            :range="getDateRangeModel(column.field)"
            :column="column.header"
            :placeholder="t('madeItems.catalogue.filters.any')"
            @update:user-id="(id) => column.userFilterParam && setFilterValue(column.userFilterParam, id)"
            @update:range="(value) => setDateRangeModel(column.field, value)"
          />
          <DatePicker
            v-else-if="column.filter === 'date-range'"
            :model-value="getDateRangeModel(column.field)"
            selection-mode="range"
            show-button-bar
            show-clear
            :placeholder="`${t('madeItems.catalogue.filters.filterBy')} ${column.header}`"
            :aria-label="t('common.filterBy', { column: column.header })"
            size="small"
            fluid
            @update:model-value="(value) => setDateRangeModel(column.field, value)"
            @clear-click="setDateRangeModel(column.field, null)"
          />
          <InputText
            v-else
            v-model="filterModel.value"
            :type="column.filter === 'number' ? 'number' : 'text'"
            @input="filterCallback()"
            :placeholder="`${t('madeItems.catalogue.filters.searchBy')} ${column.header}`"
            :aria-label="t('common.filterBy', { column: column.header })"
            size="small"
            fluid
          />
        </template>
      </Column>
    </template>
    <Column style="width: 100%" />
  </DataTable>

  <ContextMenu
    ref="cm"
    :model="contextMenuItems"
    :pt="disabledItemTooltipPt"
    @hide="contextMenuItem = null"
  />

  <MadeItemSuccessorPopover ref="successorPopover" />

  <MadeItemDetailDialog
    v-model:visible="showDetail"
    :item="detailItem"
    :edit-on-open="detailEditOnOpen"
  />
  <SourceItemDetailDialog v-model:visible="showSourceItemDetail" :item="sourceItemDetail" />
  <BoughtItemDetailDialog v-model:visible="showBoughtItemDetail" :item="boughtItemDetail" />
  <MadeItemCreateForm
    v-model:visible="showCopyForm"
    :copy-from="copyFromItem"
    @created="madeItemsStore.refresh()"
  />
  <MadeItemCreateForm
    v-model:visible="showRevisionForm"
    :revision-of="revisionOfItem"
    @created="madeItemsStore.refresh()"
  />
  <ItemChangelogDialog
    v-model:visible="showChangelogDialog"
    :item="changelogItem"
    :store="changelogStore"
    i18n-prefix="madeItems.catalogue.changelog"
  />
  <MadeItemMergeDialog v-model:visible="showMergeDialog" :item="mergeSourceItem" />
  <MadeItemDemandCreateForm v-model:visible="showDemandForm" :preset-item="demandForItem" />
  <component
    :is="lotDialogs.history"
    v-if="lotDialogs"
    v-model:visible="showHistoryDialog"
    :item="historyItem"
  />
  <FilePreviewDialog
    v-if="filePreview"
    v-model:visible="showFilePreview"
    :filename="filePreview.file.file_name"
    :mime-type="filePreview.file.mime_type"
    :fetch-blob="fetchPreviewBlob"
  />
</template>

<style lang="scss" scoped>
.catalogue-rows-clickable {
  :deep(.p-datatable-tbody) > tr {
    cursor: pointer;
  }
}

// Fills the card's flex column next to the optional PDM preview panel, and
// min-height: 0 lets it shrink to scroll internally instead of pushing the
// panel off-screen.
.mic-catalogue-table {
  flex: 1 1 auto;
  min-height: 0;
}

.group-header-label {
  font-weight: bold;
  padding-left: var(--space-4);
}
</style>
