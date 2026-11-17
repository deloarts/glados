<script setup lang="ts" generic="T extends SimpleNamedEntity, TSortBy extends string">
// The management table shared by every "simple named entity" resource, one
// with a name, a description and a colour label that is archived instead of
// deleted. A resource with a column of
// its own does not fit this component and should keep its own table.
import { ref, computed, watch } from 'vue'
import type { Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import type { DataTableFilterMeta, DataTableSortEvent } from 'openvue/datatable'

import { formatISODate as formatDate } from '@/core/utils/dates'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useServerTable } from '@/core/composables/useServerTable'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePermissions } from '@/core/composables/usePermissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useManagementResourceActions } from '@/shared/composables/useManagementResourceActions'
import ResourceDetailDialog from '@/shared/components/dialogs/ResourceDetailDialog.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import LabelTag from '@/shared/components/labels/LabelTag.vue'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import SimpleNamedEntityFormDialog from './SimpleNamedEntityFormDialog.vue'
import { useRowDragReorder } from '@/shared/composables/useRowDragReorder'
import type {
  AnyNamedEntityManagementStore,
  SimpleNamedEntity,
} from '@/shared/types/simpleNamedEntity'

interface Props {
  store: AnyNamedEntityManagementStore<T, TSortBy>
  /**
   * i18n path prefix carrying this resource's columns/filters/errors
   * strings, e.g. 'settings.articleGroups'. Every key below this prefix
   * must follow the same layout as settings.articleGroups /
   * settings.sourceItemTypes: columns.*, filters.name, showDetails,
   * errors.unknown.
   */
  i18nPrefix: string
  /**
   * Prefixes the embedded edit dialog's field ids. See
   * SimpleNamedEntityFormDialog.
   */
  idPrefix: string
  /**
   * Already-translated titles, forwarded to the embedded edit dialog and
   * used for this table's own edit tooltip/aria-label/toast.
   */
  createTitle: string
  editTitle: string
  writePermission: string
  deletePermission: string
  /**
   * Opt in to the label/font-colour contrast warning on the embedded edit
   * dialog. Only article groups show it today.
   */
  showContrastWarning?: boolean
  /** Name and description are language maps, see SimpleNamedEntityFormDialog. */
  localized?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showContrastWarning: false,
  localized: false,
})

const filters = defineModel<DataTableFilterMeta>('filters', { required: true })

const { t } = useI18n()
const { localize } = useLocalizedText()
const appToast = useAppToast()

watchLoadingBar(() => props.store.loading)
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const canWrite = computed(() => hasPermission(props.writePermission))
const canDelete = computed(() => hasPermission(props.deletePermission))

// Every resource in this table is hand-ordered: the grip in the first column
// drags a row to a new place. It shows only to users who may reorder, and
// only while the table shows the hand-kept order, since a sorted or filtered
// page has other neighbours than the order a drop would change.
const showDragHandle = computed(() => canWrite.value && props.store.manualOrder)
const { handlePt, onRowReorder } = useRowDragReorder(
  () => props.store.tableItems,
  (id, target, page) => props.store.place(id, target, page),
)

const editDialogVisible = ref(false)
const editingEntity = ref<T | undefined>(undefined) as Ref<T | undefined>

function onEdit(entity: T): void {
  editingEntity.value = entity
  editDialogVisible.value = true
}

function onSaved(entity: T): void {
  appToast.success(localize(entity.name), props.editTitle)
}

// The context menu (Edit/Show details/Delete/Copy UUID), the
// delete-confirm+toast block, and the click-or-select-opens-the-detail-dialog
// wiring below all come from the shared composable. See
// useManagementResourceActions for the behaviour this replaces line-for-line.
const {
  cm,
  contextMenuTarget: contextMenuItem,
  detailDialogVisible,
  detailTarget: detailEntity,
  contextMenuItems,
  onRowContextMenu,
  onRowClick,
  onDelete: onArchive,
  onRestore,
} = useManagementResourceActions<T>(props.store, {
  i18nPrefix: props.i18nPrefix,
  entityLabel: (entity) => localize(entity.name),
  deletePermission: props.deletePermission,
  archivable: { isArchived: (entity) => entity.archived },
  editItem: (entity) => ({
    label: props.editTitle,
    icon: 'mdi mdi-pencil',
    disabled: !canWrite.value,
    command: () => onEdit(entity),
  }),
})

// Row keyboard access: selectionMode="single" with no `v-model:selection`
// bound gives every row a tabindex and Enter-to-activate for free, via
// OpenVue's own roving-tabindex logic (BodyRow.vue#rowTabindex).
// Deliberately NOT binding `selection`: once a row is ever selected that
// computation returns -1 for every row, permanently. There's no way back
// to the null state it depends on short of unmounting. Leaving `selection`
// unbound means it never leaves null, so the table stays keyboard-reachable
// after the first row is opened. `onRowClick` above is bound to both
// @row-click and @row-select (see useRowOpenGuard for why that's safe).

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: ({ first, rows }) => ({ skip: first, limit: rows }),
  fetch: (params) => props.store.refreshTable(params),
})

watch(filters, resetAndFetchDebounced, { deep: true })
watch(() => props.store.search, resetAndFetchDebounced)

watch(
  () => props.store.clearTrigger,
  () => resetAndFetch(),
)

watch(
  () => [props.store.sortBy, props.store.sortDir],
  () => resetAndFetch(),
)

watch(
  () => props.store.showArchived,
  () => resetAndFetch(),
)

watch(
  () => props.store.refreshTrigger,
  () => fetchItems(),
)

// Server-side sort: under `lazy` OpenVue only toggles its own header icon
// and emits @sort. Nothing fetches unless we relay it into the store, whose
// sortBy/sortDir already drive buildParams()'s order_by/order_dir. Controlled
// `sortField`/`sortOrder` below (not just @sort) keeps the header icon honest
// if sort ever changes from a sibling ManagementView's own sort control,
// which writes the same store fields.
function onSort(event: DataTableSortEvent): void {
  if (typeof event.sortField === 'string' && event.sortOrder) {
    props.store.setSort(event.sortField as TSortBy, event.sortOrder === 1 ? 'asc' : 'desc')
  } else {
    props.store.clearSort()
  }
}

const detailFields = computed(() => {
  const e = detailEntity.value
  if (!e) return []
  return [
    { label: t(`${props.i18nPrefix}.columns.name`), value: localize(e.name) },
    { label: t(`${props.i18nPrefix}.columns.description`), value: localize(e.description) || null },
    { label: t(`${props.i18nPrefix}.columns.creator`), value: e.creator?.full_name ?? null },
    { label: t(`${props.i18nPrefix}.columns.created`), value: formatDate(e.created) },
    {
      label: t(`${props.i18nPrefix}.columns.changed`),
      value: formatDate(e.changed),
    },
    {
      label: t(`${props.i18nPrefix}.columns.archived`),
      value: e.archived ? t('common.yes') : t('common.no'),
    },
  ]
})
</script>

<template>
  <DataTable
    :value="store.tableItems"
    v-model:filters="filters"
    v-model:context-menu-selection="contextMenuItem"
    filter-display="row"
    data-key="id"
    lazy
    paginator
    :total-records="store.total"
    :first="first"
    :rows="rows"
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    @page="onPage"
    :sort-field="store.sortBy ?? undefined"
    :sort-order="store.sortBy ? (store.sortDir === 'asc' ? 1 : -1) : undefined"
    removable-sort
    @sort="onSort"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    scrollable
    scroll-height="flex"
    resizable-columns
    column-resize-mode="fit"
    class="simple-named-entity-table simple-named-entity-rows-clickable"
    selection-mode="single"
    @row-reorder="onRowReorder"
    @row-contextmenu="onRowContextMenu"
    @row-click="onRowClick"
    @row-select="onRowClick"
  >
    <Column
      v-if="showDragHandle"
      row-reorder
      row-reorder-icon="mdi mdi-drag-vertical"
      :pt="handlePt"
      class="column-fit"
    />
    <Column
      v-if="store.showActions"
      :header="t(`${i18nPrefix}.columns.actions`)"
      class="column-fit"
    >
      <template #body="{ data }: { data: T }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            :disabled="!canWrite"
            v-tooltip.top.focus="editTitle"
            :aria-label="editTitle"
            @click.stop="onEdit(data)"
          />
          <Button
            v-if="!data.archived"
            icon="mdi mdi-archive-outline"
            size="small"
            severity="danger"
            text
            :disabled="!canDelete"
            v-tooltip.top.focus="t('common.archive')"
            :aria-label="t('common.archive')"
            @click.stop="onArchive(data)"
          />
          <Button
            v-else
            icon="mdi mdi-archive-arrow-up-outline"
            size="small"
            severity="secondary"
            text
            :disabled="!canDelete"
            v-tooltip.top.focus="t('common.restore')"
            :aria-label="t('common.restore')"
            @click.stop="onRestore(data)"
          />
        </div>
      </template>
    </Column>
    <Column header="#" header-style="width: 3rem" body-class="row-number">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>
    <Column
      field="name"
      :header="t(`${i18nPrefix}.columns.name`)"
      :show-filter-menu="false"
      sortable
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t(`${i18nPrefix}.filters.name`)"
          :aria-label="t('common.filterBy', { column: t(`${i18nPrefix}.columns.name`) })"
          size="small"
          fluid
        />
      </template>
      <template #body="{ data }: { data: T }">{{ localize(data.name) }}</template>
    </Column>
    <Column
      field="description"
      :header="t(`${i18nPrefix}.columns.description`)"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: T }">
        <span v-if="localize(data.description)">{{ localize(data.description) }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t(`${i18nPrefix}.columns.label`)" style="width: 10rem">
      <template #body="{ data }: { data: T }">
        <LabelTag :label="data" />
      </template>
    </Column>
    <Column :header="t(`${i18nPrefix}.columns.archived`)" style="width: 8rem">
      <template #body="{ data }: { data: T }">
        <Tag
          v-if="data.archived"
          :value="t('common.archivedTag')"
          severity="warn"
          icon="mdi mdi-archive-outline"
          v-tooltip.top="t('common.archivedTagTooltip')"
        />
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column
      field="created"
      :header="t(`${i18nPrefix}.columns.created`)"
      sortable
      style="width: 8rem"
    >
      <template #body="{ data }: { data: T }">
        <UserDateCell :date="data.created" :user="data.creator" />
      </template>
    </Column>
    <Column :header="t(`${i18nPrefix}.columns.changed`)" style="width: 8rem">
      <template #body="{ data }: { data: T }">
        <UserDateCell :date="data.changed" :user="data.changed_by" />
      </template>
    </Column>
    <Column style="width: 100%" />

    <template #empty>
      <EmptyState />
    </template>
  </DataTable>

  <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />

  <SimpleNamedEntityFormDialog
    v-model:visible="editDialogVisible"
    :entity="editingEntity"
    :id-prefix="idPrefix"
    :i18n-prefix="i18nPrefix"
    :create-title="createTitle"
    :edit-title="editTitle"
    :show-contrast-warning="showContrastWarning"
    :localized="localized"
    :store="store"
    @saved="onSaved"
  />

  <ResourceDetailDialog
    v-model:visible="detailDialogVisible"
    :title="t(`${i18nPrefix}.showDetails`)"
    :fields="detailFields"
  />
</template>

<style scoped lang="scss">
.simple-named-entity-table {
  width: 100%;
}

.simple-named-entity-rows-clickable {
  :deep(.p-datatable-tbody) > tr {
    cursor: pointer;
  }
}
</style>
