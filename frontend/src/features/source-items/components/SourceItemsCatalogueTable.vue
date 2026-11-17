<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAppToast } from '@/core/composables/useAppToast'
import { useConfirm } from 'openvue/useconfirm'
import {
  TABLE_ROWS_PER_PAGE_OPTIONS,
  TABLE_COL_WIDTH_ID,
  TABLE_COL_WIDTH_STATUS,
} from '@/core/constants/table'
import { useI18n } from 'vue-i18n'
import { useServerTable } from '@/core/composables/useServerTable'
import { extractApiError } from '@/core/utils/errors'
import { usePrint } from '@/shared/print'
import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'

import { sourceItemsApi } from '../api/sourceItemsApi'
import { getSourceItemFileBlob } from '../api/sourceItemFilesApi'
import { useSourceItemsStore } from '../stores/sourceItemsStore'
import { useSourceItemsCatalogueEditStore } from '../stores/sourceItemsCatalogueEditStore'
import { useSourceItemsCatalogueFiltersStore } from '../stores/sourceItemsCatalogueFiltersStore'
import { useSourceItemsCatalogueViewStore } from '../stores/sourceItemsCatalogueViewStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { Permission } from '@/core/auth/permissions'
import { useCatalogueRowSelection } from '@/shared/composables/useCatalogueRowSelection'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import { useSourceItemsCatalogueContextMenu } from '../composables/useSourceItemsCatalogueContextMenu'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'
import SourceItemDetailDialog from './SourceItemDetailDialog.vue'
import SourceItemThumbnailCell from './SourceItemThumbnailCell.vue'
import SourceItemFilesCell from './SourceItemFilesCell.vue'
import { useHostStore } from '@/core/host/stores/hostStore'
import { SupplierSearchFilter } from '@/features/suppliers'
import { useSourceItemTypesStore } from '@/features/source-item-types'
import { useLayoutStore } from '@/core/stores/layoutStore'
import {
  SOURCE_ITEM_STATUS_OPTIONS,
  toSourceItemFilterParams,
  toDateRangeFilterParams,
  useSourceItemsCatalogueColumnsStore,
} from '../stores/sourceItemsCatalogueColumnsStore'

import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { SourceItemResponse, SourceItemFile } from '../types/sourceItemsResponse'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useKeyedDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { useKeyedFilterMetaModel } from '@/shared/composables/useFilterMetaModel'
import { catalogueStatusTagSeverity } from '@/shared/utils/catalogueStatus'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import { labelName } from '@/shared/utils/localizeLabel'

const { t } = useI18n()
const { localize } = useLocalizedText()
const router = useRouter()
const toast = useAppToast()
const printService = usePrint()
const confirm = useConfirm()
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const canWrite = computed(() => hasPermission(Permission.WRITE_SOURCE_ITEMS))
const canDelete = computed(() => hasPermission(Permission.DELETE_SOURCE_ITEMS))
const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))

const statusOptions = computed(() =>
  SOURCE_ITEM_STATUS_OPTIONS.map((s) => ({
    label: t(`sourceItems.catalogue.status.${s}`),
    value: s,
  })),
)

const sourceItemsStore = useSourceItemsStore()
const columnsStore = useSourceItemsCatalogueColumnsStore()
const editStore = useSourceItemsCatalogueEditStore()
const filtersStore = useSourceItemsCatalogueFiltersStore()
const viewStore = useSourceItemsCatalogueViewStore()
const sourceItemTypesStore = useSourceItemTypesStore()

watchLoadingBar(() => sourceItemsStore.loading)

const groupedItems = computed(() => {
  const items = sourceItemsStore.items
  if (!viewStore.groupBy) return items

  return [...items].sort((a, b) => {
    const aValue = viewStore.groupBy === 'status' ? a.status : (a.manufacturer_name ?? '')
    const bValue = viewStore.groupBy === 'status' ? b.status : (b.manufacturer_name ?? '')
    return aValue.localeCompare(bValue)
  })
})

const groupRowsBy = computed(() => (viewStore.groupBy ? viewStore.groupBy : undefined))

const { isSelectionColumnVisible, tableSelectionProps, onRowClick, onRowSelect, onSelectionUpdate } =
  useCatalogueRowSelection<SourceItemResponse>({
    editStore,
    canSelect: () => canWrite.value,
    openDetail: (item) => navigateToDetail(item),
  })

function navigateToDetail(item: SourceItemResponse): void {
  void router.push(`/catalogue/source-items/${item.id}`)
}

const { filters, dateRangeFilters, search, showArchived, clearTrigger } = storeToRefs(filtersStore)
const { sortBy, sortDir } = storeToRefs(viewStore)

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage, onFilter } =
  useServerTable({
    fetchParams: ({ first, rows }) => ({
      skip: first,
      limit: rows,
      ...(search.value ? { search: search.value } : {}),
      ...toSourceItemFilterParams(filters.value),
      ...toDateRangeFilterParams(dateRangeFilters.value),
      ...(sortBy.value ? { order_by: sortBy.value, order_dir: sortDir.value } : {}),
      ...(showArchived.value ? { include_archived: true } : {}),
    }),
    fetch: (params) => sourceItemsStore.refresh(params),
  })

const { getDateRangeModel, setDateRangeModel } = useKeyedDateRangeFilter(dateRangeFilters, onFilter)
const { getFilterValue, setFilterValue } = useKeyedFilterMetaModel(filters, onFilter)

const FIXED_COLUMN_WIDTHS: Record<string, string> = {
  id: TABLE_COL_WIDTH_ID,
  image: '3.25rem',
  files: '9rem',
  status: TABLE_COL_WIDTH_STATUS,
}

const hostStore = useHostStore()

// The thumbnail and files columns have nothing to show with storage off.
const visibleColumns = computed(() =>
  hostStore.storageEnabled
    ? columnsStore.visibleColumns
    : columnsStore.visibleColumns.filter((c) => c.field !== 'image' && c.field !== 'files'),
)

function columnWidth(field: string): string {
  return FIXED_COLUMN_WIDTHS[field] ?? '10%'
}

function typeTagStyle(typeId: number): Record<string, string> | undefined {
  const type = sourceItemTypesStore.getById(typeId)
  if (!type) return undefined
  return { background: type.label_color, color: type.label_font_color }
}

watch(search, resetAndFetchDebounced)

watch(showArchived, resetAndFetch)

watch(clearTrigger, resetAndFetch)

watch(
  () => sourceItemsStore.refreshTrigger,
  () => fetchItems(),
)

watch([sortBy, sortDir], resetAndFetch)

onMounted(() => {
  if (sourceItemTypesStore.items.length === 0) {
    void sourceItemTypesStore.refresh()
  }
})

// ── Detail dialog ───────────────────────────────────────────────────────
// A row click navigates to the detail page; the dialog only serves the
// context menu's Edit entry.

const detailItem = ref<SourceItemResponse | null>(null)
const showDetail = ref(false)
const detailEditOnOpen = ref(false)

function openDetailForEdit(item: SourceItemResponse): void {
  detailItem.value = item
  detailEditOnOpen.value = true
  showDetail.value = true
}

// ── Context menu ────────────────────────────────────────────────────────

const cm = ref()
const contextMenuItem = ref<SourceItemResponse | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

function editItem(item: SourceItemResponse): void {
  editStore.editMode = true
  editStore.selectedItems = [item]
}

function onArchiveItem(item: SourceItemResponse): void {
  async function onAccept(): Promise<void> {
    try {
      await sourceItemsStore.archive(item.id)
      toast.success(localize(item.type_name), t('common.archive'))
    } catch (e) {
      toast.error(localize(item.type_name), extractApiError(e) ?? t('sourceItems.edit.errors.unknown'))
    }
  }

  confirm.require({
    message: t('common.archiveConfirm', { name: localize(item.type_name) }),
    header: t('common.archive'),
    icon: 'mdi mdi-archive-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('common.archive'), severity: 'warn' },
    accept: () => void onAccept(),
  })
}

async function onRestoreItem(item: SourceItemResponse): Promise<void> {
  try {
    await sourceItemsStore.restore(item.id)
    toast.success(localize(item.type_name), t('common.restore'))
  } catch (e) {
    toast.error(localize(item.type_name), extractApiError(e) ?? t('sourceItems.edit.errors.unknown'))
  }
}

const printingItemId = ref<number | null>(null)

async function onPrintLabel(item: SourceItemResponse): Promise<void> {
  printingItemId.value = item.id
  try {
    const [job] = await printService.print({
      root_type: 'source_item',
      root_id: item.id,
      items: [{ classifier: 'source_item_label' }],
    })
    if (job?.status === 'sent') {
      toast.success(localize(item.type_name), t('sourceItems.edit.contextMenu.printLabelSent'))
    } else {
      toast.error(
        localize(item.type_name),
        job?.error_message ?? t('sourceItems.edit.contextMenu.printLabelFailed'),
      )
    }
  } catch (e) {
    toast.error(
      localize(item.type_name),
      extractApiError(e) ?? t('sourceItems.edit.contextMenu.printLabelFailed'),
    )
  } finally {
    printingItemId.value = null
  }
}

const { contextMenuItems } = useSourceItemsCatalogueContextMenu({
  contextMenuItem,
  canWrite,
  canDelete,
  canPrint,
  printingItemId,
  openDetailForEdit,
  onPrintLabel,
  onRestoreItem,
  onArchiveItem,
})

const successorPopover = ref()
const successorPopoverItem = ref<SourceItemResponse | null>(null)
const successorPopoverLoading = ref(false)

function onSuccessorTagClickFor(event: Event, item: SourceItemResponse): void {
  if (item.successor_item_id) void onSuccessorTagClick(event, item.successor_item_id)
}

async function onSuccessorTagClick(event: Event, id: number): Promise<void> {
  successorPopoverItem.value = null
  successorPopoverLoading.value = true
  successorPopover.value.show(event)

  const cached = sourceItemsStore.getById(id)
  if (cached) {
    successorPopoverItem.value = cached
    successorPopoverLoading.value = false
    return
  }

  const result = await sourceItemsApi.list({ id, limit: 1 })
  successorPopoverItem.value = result.items[0] ?? null
  successorPopoverLoading.value = false
}

// ── Files column preview ─────────────────────────────────────────────

interface FilePreviewTarget {
  itemId: number
  file: SourceItemFile
}

const filePreview = ref<FilePreviewTarget | null>(null)
const showFilePreview = ref(false)

function openFilePreview(itemId: number, file: SourceItemFile): void {
  filePreview.value = { itemId, file }
  showFilePreview.value = true
}

function fetchPreviewBlob(): Promise<Blob> {
  const target = filePreview.value
  if (!target) return Promise.reject(new Error('no file selected for preview'))
  return getSourceItemFileBlob(target.itemId, target.file.id)
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
    :total-records="sourceItemsStore.total"
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
    class="phone-columns catalogue-rows-clickable"
  >
    <template v-if="viewStore.groupBy" #groupheader="{ data }">
      <div class="group-header">
        <i v-if="viewStore.groupBy === 'manufacturer_name'" class="mdi mdi-cart" aria-hidden="true" />
        <i v-else class="mdi mdi-tag" aria-hidden="true" />
        <span class="group-header-label">{{
          viewStore.groupBy === 'manufacturer_name' ? data.manufacturer_name : data.status
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
    <Column v-if="viewStore.showActions" style="width: 6rem" frozen align-frozen="right">
      <template #body="{ data }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            rounded
            :disabled="!canWrite"
            v-tooltip.focus="t('sourceItems.catalogue.controls.edit')"
            :aria-label="t('sourceItems.catalogue.controls.edit')"
            @click="editItem(data as SourceItemResponse)"
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

    <template v-for="column in visibleColumns" :key="column.field">
      <Column
        :field="column.field"
        :header="column.header"
        :class="column.phoneClass"
        :show-filter-menu="false"
        :style="{ width: columnWidth(column.field) }"
      >
        <template
          v-if="
            column.field === 'image' ||
            column.field === 'files' ||
            column.field === 'status' ||
            column.field === 'successor_item_id' ||
            column.field === 'created' ||
            column.field === 'changed' ||
            column.field === 'type_name'
          "
          #body="{ data }"
        >
          <SourceItemThumbnailCell
            v-if="column.field === 'image'"
            :item-id="(data as SourceItemResponse).id"
            :item-name="(data as SourceItemResponse).dimension ?? undefined"
            :dimension="(data as SourceItemResponse).dimension"
          />
          <SourceItemFilesCell
            v-if="column.field === 'files'"
            :item-id="(data as SourceItemResponse).id"
            @preview="(file) => openFilePreview((data as SourceItemResponse).id, file)"
          />
          <UserDateCell
            v-if="column.field === 'created'"
            :date="(data as SourceItemResponse).created"
            :user="(data as SourceItemResponse).creator"
          />
          <UserDateCell
            v-if="column.field === 'changed'"
            :date="(data as SourceItemResponse).changed"
            :user="(data as SourceItemResponse).changed_by"
          />
          <div v-if="column.field === 'status'" class="state-cell">
            <Tag
              :value="t(`sourceItems.catalogue.status.${data.status}`)"
              :severity="catalogueStatusTagSeverity(data.status)"
            />
            <Tag
              v-if="(data as SourceItemResponse).archived"
              :value="t('common.archivedTag')"
              severity="warn"
              icon="mdi mdi-archive-outline"
              v-tooltip.top="t('common.archivedTagTooltip')"
            />
          </div>
          <div v-if="column.field === 'successor_item_id'" class="successor-cell">
            <Tag
              v-if="(data as SourceItemResponse).successor_item_id"
              :value="`#${(data as SourceItemResponse).successor_item_id}`"
              severity="secondary"
              class="successor-tag"
              role="button"
              tabindex="0"
              @click.stop="onSuccessorTagClickFor($event, data as SourceItemResponse)"
              @keydown.enter="onSuccessorTagClickFor($event, data as SourceItemResponse)"
              @keydown.space.prevent="onSuccessorTagClickFor($event, data as SourceItemResponse)"
            />
          </div>
          <Tag
            v-if="column.field === 'type_name'"
            :value="localize((data as SourceItemResponse).type_name)"
            :style="typeTagStyle((data as SourceItemResponse).type_id)"
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
            :placeholder="t('sourceItems.catalogue.filters.any')"
            :aria-label="t('common.filterBy', { column: column.header })"
            size="small"
            fluid
            @change="filterCallback()"
            @clear="filterCallback()"
          />
          <SupplierSearchFilter
            v-else-if="column.filter === 'supplier'"
            v-model="filterModel.value"
            @update:model-value="filterCallback()"
            :placeholder="t('sourceItems.catalogue.filters.any')"
            :aria-label="t('common.filterBy', { column: column.header })"
          />
          <Select
            v-else-if="column.filter === 'source-item-type'"
            v-model="filterModel.value"
            :options="sourceItemTypesStore.items"
            :option-label="labelName"
            option-value="id"
            :loading="sourceItemTypesStore.loading"
            show-clear
            :placeholder="t('sourceItems.catalogue.filters.any')"
            :aria-label="t('common.filterBy', { column: column.header })"
            size="small"
            filter
            fluid
            @change="filterCallback()"
            @clear="filterCallback()"
          />
          <UserDateFilter
            v-else-if="column.filter === 'date-range' && column.userFilterParam"
            :user-id="getFilterValue<number>(column.userFilterParam)"
            :range="getDateRangeModel(column.field)"
            :column="column.header"
            :placeholder="t('sourceItems.catalogue.filters.any')"
            @update:user-id="(id) => column.userFilterParam && setFilterValue(column.userFilterParam, id)"
            @update:range="(value) => setDateRangeModel(column.field, value)"
          />
          <DatePicker
            v-else-if="column.filter === 'date-range'"
            :model-value="getDateRangeModel(column.field)"
            selection-mode="range"
            show-button-bar
            show-clear
            :placeholder="`${t('sourceItems.catalogue.filters.filterBy')} ${column.header}`"
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
            :placeholder="`${t('sourceItems.catalogue.filters.searchBy')} ${column.header}`"
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

  <Popover ref="successorPopover">
    <div class="successor-popover">
      <div v-if="successorPopoverLoading" class="successor-popover-loading">
        <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
      </div>
      <template v-else-if="successorPopoverItem">
        <div class="successor-popover-row">
          <span class="successor-popover-label">{{ t('sourceItems.catalogue.columns.id') }}</span>
          <span>{{ successorPopoverItem.id }}</span>
        </div>
        <div class="successor-popover-row">
          <span class="successor-popover-label">{{
            t('sourceItems.catalogue.columns.type')
          }}</span>
          <span>{{ localize(successorPopoverItem.type_name) || getEmptyPlaceholder() }}</span>
        </div>
        <div class="successor-popover-row">
          <span class="successor-popover-label">{{
            t('sourceItems.catalogue.columns.manufacturer')
          }}</span>
          <span>{{ successorPopoverItem.manufacturer_name }}</span>
        </div>
      </template>
    </div>
  </Popover>

  <SourceItemDetailDialog
    v-model:visible="showDetail"
    :item="detailItem"
    :edit-on-open="detailEditOnOpen"
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

.state-cell {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.successor-tag {
  cursor: pointer;

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: 2px;
  }
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
