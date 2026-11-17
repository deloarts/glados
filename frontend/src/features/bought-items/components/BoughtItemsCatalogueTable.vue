<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import LabelTag from '@/shared/components/labels/LabelTag.vue'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import { useBoughtItemsStore } from '../stores/boughtItemsStore'
import { useBoughtItemsCatalogueViewStore } from '../stores/boughtItemsCatalogueViewStore'
import { useBoughtItemsCatalogueColumnsStore } from '../stores/boughtItemsCatalogueColumnsStore'
import { useBoughtItemsChangelogStore } from '../stores/boughtItemsChangelogStore'
import { useBoughtItemsCatalogueDialogs } from '../composables/useBoughtItemsCatalogueDialogs'
import { useBoughtItemsCatalogueRowActions } from '../composables/useBoughtItemsCatalogueRowActions'
import { useBoughtItemsCatalogueSelection } from '../composables/useBoughtItemsCatalogueSelection'
import { useBoughtItemsCatalogueSuccessorPopover } from '../composables/useBoughtItemsCatalogueSuccessorPopover'
import { useBoughtItemsCatalogueContextMenu } from '../composables/useBoughtItemsCatalogueContextMenu'
import { useBoughtItemsCatalogueFilters } from '../composables/useBoughtItemsCatalogueFilters'

import { useBoughtItemOrderDialogs } from '../composables/useBoughtItemOrderDialogs'
import BoughtItemDetailDialog from './BoughtItemDetailDialog.vue'
import ItemChangelogDialog from '@/shared/components/items/ItemChangelogDialog.vue'
import BoughtItemCreateForm from './BoughtItemCreateForm.vue'
import BoughtItemDemandCreateForm from './BoughtItemDemandCreateForm.vue'
import BoughtItemMergeDialog from './BoughtItemMergeDialog.vue'
import BoughtItemThumbnailCell from './BoughtItemThumbnailCell.vue'
import BoughtItemRowActionsCell from './catalogue-table/BoughtItemRowActionsCell.vue'
import BoughtItemStatusCell from './catalogue-table/BoughtItemStatusCell.vue'
import BoughtItemArticleGroupsCell from './catalogue-table/BoughtItemArticleGroupsCell.vue'
import BoughtItemSuccessorCell from './catalogue-table/BoughtItemSuccessorCell.vue'
import BoughtItemWeblinkCell from './catalogue-table/BoughtItemWeblinkCell.vue'
import BoughtItemPdfFilesCell from './catalogue-table/BoughtItemPdfFilesCell.vue'
import BoughtItemPartNumberCell from './catalogue-table/BoughtItemPartNumberCell.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'
import BoughtItemRevisionCell from './catalogue-table/BoughtItemRevisionCell.vue'
import BoughtItemColumnFilter from './catalogue-table/BoughtItemColumnFilter.vue'
import BoughtItemDataSourceCell from './catalogue-table/BoughtItemDataSourceCell.vue'
import { columnWidth, BOUGHT_ITEM_CUSTOM_BODY_FIELDS } from './catalogue-table/boughtItemsCatalogueColumns'

import type { BoughtItemResponse } from '../types/boughtItemsResponse'

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const { hasPermission } = usePermissions()

const canWrite = computed(() => hasPermission(Permission.WRITE_BOUGHT_ITEMS))
const canDelete = computed(() => hasPermission(Permission.DELETE_BOUGHT_ITEMS))
const canCreateDemand = computed(() => hasPermission(Permission.WRITE_DEMAND_ITEMS))
const canWriteOrders = computed(() => hasPermission(Permission.WRITE_ORDERS))
const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))

const boughtItemsStore = useBoughtItemsStore()
const hostStore = useHostStore()

watchLoadingBar(() => boughtItemsStore.loading)
const columnsStore = useBoughtItemsCatalogueColumnsStore()

// The thumbnail sits directly after the leading identity columns. It follows
// data_source when that column is shown and falls back to status otherwise,
// so hiding data_source moves the thumbnail rather than dropping it.
const thumbnailAnchorField = computed(() =>
  columnsStore.visibleColumns.some((column) => column.field === 'data_source')
    ? 'data_source'
    : 'status',
)
const viewStore = useBoughtItemsCatalogueViewStore()
const changelogStore = useBoughtItemsChangelogStore()

const {
  filters,
  groupedItems,
  groupRowsBy,
  first,
  rows,
  onPage,
  onFilter,
  getDateRangeModel,
  setDateRangeModel,
  getFilterValue,
  setFilterValue,
} = useBoughtItemsCatalogueFilters()

const { isSelectionColumnVisible, tableSelectionProps, onSelectionUpdate, onRowClick, onRowSelect } =
  useBoughtItemsCatalogueSelection(() => canWrite.value)

const {
  orderHistoryItem,
  showOrderHistory,
  openOrderHistory,
  detailItem,
  showDetail,
  detailEditOnOpen,
  openDetailForEdit,
  copyFromItem,
  showCopyForm,
  copyItem,
  mergeSourceItem,
  showMergeDialog,
  mergeItem,
  demandPresetItem,
  showDemandForm,
  createDemandFor,
  addToOrderItem,
  showAddToOrder,
  addItemToOrder,
  changelogItem,
  showChangelogDialog,
  showChangelogFor,
  previewFile,
  previewItemId,
  showFilePreview,
  openPdf,
  fetchPdfBlob,
} = useBoughtItemsCatalogueDialogs()

// Adding to an order and the order history come from the hosting page.
const orderDialogs = useBoughtItemOrderDialogs()

const { editItem, onArchiveItem, onRestoreItem, printingItemId, onPrintLabel } =
  useBoughtItemsCatalogueRowActions()

const { successorPopover, successorPopoverItem, successorPopoverLoading, onSuccessorTagClick } =
  useBoughtItemsCatalogueSuccessorPopover()

const { cm, contextMenuItem, onRowContextMenu, contextMenuItems, disabledItemTooltipPt } =
  useBoughtItemsCatalogueContextMenu({
    canWrite,
    canDelete,
    canCreateDemand,
    canWriteOrders,
    canPrint,
    printingItemId,
    openDetailForEdit,
    copyItem,
    mergeItem,
    onRestoreItem,
    onArchiveItem,
    createDemandFor,
    addItemToOrder,
    openOrderHistory,
    showChangelogFor,
    onPrintLabel,
  })
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
    :total-records="boughtItemsStore.total"
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
    class="phone-columns catalogue-rows-clickable bic-catalogue-table"
  >
    <template v-if="viewStore.groupBy" #groupheader="{ data }">
      <div class="group-header">
        <i v-if="viewStore.groupBy === 'manufacturer_name'" class="mdi mdi-cart" aria-hidden="true" />
        <i v-else class="mdi mdi-tag" aria-hidden="true" />
        <span class="group-header-label">{{
          viewStore.groupBy === 'manufacturer_name' ? data.manufacturer_name : data._categoryGroup
        }}</span>
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
    <Column v-if="viewStore.showActions" style="width: 16rem" frozen align-frozen="right">
      <template #body="{ data }">
        <BoughtItemRowActionsCell
          :item="data as BoughtItemResponse"
          :can-write="canWrite"
          :can-delete="canDelete"
          :can-create-demand="canCreateDemand"
          :can-write-orders="canWriteOrders"
          @edit="editItem"
          @copy="copyItem"
          @merge="mergeItem"
          @create-demand="createDemandFor"
          @add-to-order="addItemToOrder"
          @view-order-history="openOrderHistory"
          @show-changelog="showChangelogFor"
        />
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

    <template v-for="column in columnsStore.visibleColumns" :key="column.field">
      <Column
        :field="column.field"
        :header="column.header"
        :class="column.phoneClass"
        :show-filter-menu="false"
        :style="{ width: columnWidth(column.field) }"
      >
        <template v-if="BOUGHT_ITEM_CUSTOM_BODY_FIELDS.has(column.field)" #body="{ data }">
          <BoughtItemStatusCell v-if="column.field === 'status'" :item="data as BoughtItemResponse" />
          <BoughtItemArticleGroupsCell
            v-else-if="column.field === 'article_groups'"
            :item="data as BoughtItemResponse"
          />
          <LabelTag
            v-else-if="column.field === 'product_family'"
            :label="(data as BoughtItemResponse).product_family"
          />
          <BoughtItemSuccessorCell
            v-else-if="column.field === 'successor_item_id'"
            :item="data as BoughtItemResponse"
            @click="onSuccessorTagClick"
          />
          <BoughtItemWeblinkCell v-else-if="column.field === 'weblink'" :item="data as BoughtItemResponse" />
          <BoughtItemPdfFilesCell
            v-else-if="column.field === 'pdf_files'"
            :item="data as BoughtItemResponse"
            @open-pdf="(file) => openPdf(data as BoughtItemResponse, file)"
          />
          <BoughtItemPartNumberCell
            v-else-if="column.field === 'part_number'"
            :item="data as BoughtItemResponse"
          />
          <UserDateCell
            v-else-if="column.field === 'created'"
            :date="(data as BoughtItemResponse).created"
            :user="(data as BoughtItemResponse).creator"
          />
          <UserDateCell
            v-else-if="column.field === 'changed'"
            :date="(data as BoughtItemResponse).changed"
            :user="(data as BoughtItemResponse).changed_by"
          />
          <BoughtItemRevisionCell v-else-if="column.field === 'revision'" :item="data as BoughtItemResponse" />
          <BoughtItemDataSourceCell
            v-else-if="column.field === 'data_source'"
            :item="data as BoughtItemResponse"
          />
        </template>

        <template v-if="column.filter" #filter="{ filterModel, filterCallback }">
          <UserDateFilter
            v-if="column.userFilterParam"
            :user-id="getFilterValue<number>(column.userFilterParam)"
            :range="getDateRangeModel(column.field)"
            :column="column.header"
            :placeholder="t('boughtItems.catalogue.filters.any')"
            @update:user-id="(id) => column.userFilterParam && setFilterValue(column.userFilterParam, id)"
            @update:range="(value) => setDateRangeModel(column.field, value)"
          />
          <BoughtItemColumnFilter
            v-else
            :column="column"
            :model-value="filterModel.value"
            @update:model-value="(v) => (filterModel.value = v)"
            :filter-callback="filterCallback"
            :get-date-range-model="getDateRangeModel"
            :set-date-range-model="setDateRangeModel"
          />
        </template>
      </Column>
      <Column
        v-if="column.field === thumbnailAnchorField && hostStore.storageEnabled"
        class="phone-thumbnail"
        style="width: 3.25rem; min-width: 3.25rem; padding: var(--space-1) var(--space-2)"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <BoughtItemThumbnailCell
            :item-id="(data as BoughtItemResponse).id"
            :item-name="(data as BoughtItemResponse).article_name"
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

  <Popover ref="successorPopover">
    <div class="successor-popover">
      <div v-if="successorPopoverLoading" class="successor-popover-loading">
        <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
      </div>
      <template v-else-if="successorPopoverItem">
        <div class="successor-popover-row">
          <span class="successor-popover-label">{{ t('boughtItems.catalogue.columns.id') }}</span>
          <span>{{ successorPopoverItem.id }}</span>
        </div>
        <div class="successor-popover-row">
          <span class="successor-popover-label">{{
            t('boughtItems.catalogue.columns.articleName')
          }}</span>
          <span>{{ successorPopoverItem.article_name }}</span>
        </div>
        <div class="successor-popover-row">
          <span class="successor-popover-label">{{
            t('boughtItems.catalogue.columns.partNumber')
          }}</span>
          <span>{{ successorPopoverItem.part_number ?? getEmptyPlaceholder() }}</span>
        </div>
        <div class="successor-popover-row">
          <span class="successor-popover-label">{{
            t('boughtItems.catalogue.columns.orderCode1')
          }}</span>
          <span>{{ successorPopoverItem.order_code_1 }}</span>
        </div>
        <div class="successor-popover-row">
          <span class="successor-popover-label">{{
            t('boughtItems.catalogue.columns.manufacturer')
          }}</span>
          <span>{{ successorPopoverItem.manufacturer_name }}</span>
        </div>
      </template>
    </div>
  </Popover>

  <component
    :is="orderDialogs.orderHistory"
    v-if="orderDialogs"
    v-model:visible="showOrderHistory"
    :item="orderHistoryItem"
  />
  <BoughtItemDetailDialog
    v-model:visible="showDetail"
    :item="detailItem"
    :edit-on-open="detailEditOnOpen"
  />
  <BoughtItemCreateForm
    v-model:visible="showCopyForm"
    :copy-from="copyFromItem"
    @created="boughtItemsStore.refresh()"
  />
  <BoughtItemDemandCreateForm v-model:visible="showDemandForm" :preset-item="demandPresetItem" />
  <component
    :is="orderDialogs.addToOrder"
    v-if="orderDialogs"
    v-model:visible="showAddToOrder"
    :item="addToOrderItem"
  />
  <ItemChangelogDialog
    v-model:visible="showChangelogDialog"
    :item="changelogItem"
    :store="changelogStore"
    i18n-prefix="boughtItems.catalogue.changelog"
  />
  <BoughtItemMergeDialog v-model:visible="showMergeDialog" :item="mergeSourceItem" />
  <FilePreviewDialog
    v-if="previewFile"
    v-model:visible="showFilePreview"
    :filename="previewFile.file_name"
    :mime-type="previewFile.mime_type"
    :fetch-blob="() => fetchPdfBlob(previewItemId!, previewFile!.id)"
  />
</template>

<style lang="scss" scoped>
.catalogue-rows-clickable {
  :deep(.p-datatable-tbody) > tr {
    cursor: pointer;
  }
}

// See MadeItemsCatalogueTable.vue's identical rule for the reasoning: this
// table must claim the remaining flex-column height whether it's the
// card's sole child or shares it with the PDM preview panel above it.
.bic-catalogue-table {
  flex: 1 1 auto;
  min-height: 0;
}

.successor-popover {
  min-width: 16rem;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.successor-popover-loading {
  display: flex;
  justify-content: center;
  padding: var(--space-2);
}

.successor-popover-row {
  display: flex;
  gap: var(--space-3);
  align-items: baseline;
}

.successor-popover-label {
  flex-shrink: 0;
  width: 7rem;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.group-header-label {
  font-weight: bold;
  padding-left: var(--space-4);
}
</style>
