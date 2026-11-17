<script setup lang="ts">
import { formatAddress } from '@/shared/utils/address'
import { onMounted, ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { storeToRefs } from 'pinia'
import type { DataTableSortEvent } from 'openvue/datatable'
import { formatISODate as formatDate } from '@/core/utils/dates'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useServerTable } from '@/core/composables/useServerTable'
import { useManagementResourceActions } from '@/shared/composables/useManagementResourceActions'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { useFilterMetaModel } from '@/shared/composables/useFilterMetaModel'
import { useFilterMetaWatch } from '@/shared/composables/useFilterMetaWatch'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import { useUsersStore } from '@/core/stores/usersStore'
import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import { useArticleGroupsStore } from '@/features/article-groups'

import { useSuppliersStore } from '../stores/suppliersStore'
import SupplierFormDialog from './SupplierFormDialog.vue'
import ResourceDetailDialog from '@/shared/components/dialogs/ResourceDetailDialog.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import type { SupplierResponse } from '../types/supplierResponse'
import type { SupplierSortBy } from '../types/supplierRequest'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ContactLinks from '@/shared/components/ContactLinks.vue'
import { groupRowsByLabel } from '@/core/utils/tableRowGrouping'
import LabelTag from '@/shared/components/labels/LabelTag.vue'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const { t } = useI18n()
const toast = useAppToast()

const store = useSuppliersStore()
const {
  tableItems: items,
  loading,
  filters,
  clearTrigger,
  search,
  sortBy,
  sortDir,
  groupBy,
  showArchived,
  createdFrom,
  createdTo,
  changedFrom,
  changedTo,
} = storeToRefs(store)
watchLoadingBar(loading)
const usersStore = useUsersStore()
const fabricationMethodsStore = useFabricationMethodsStore()
const articleGroupsStore = useArticleGroupsStore()

// Archived capabilities and article groups stay selectable, sorted last.
const { sortedOptions: capabilityFilterOptions } = useArchivableOptions(
  computed(() => fabricationMethodsStore.items),
)
const { sortedOptions: articleGroupFilterOptions } = useArchivableOptions(
  computed(() => articleGroupsStore.items),
)
const levelOptions = ['A', 'B', 'C'].map((level) => ({ label: level, value: level }))
const createdRange = useDateRangeFilter(createdFrom, createdTo)
const creatorId = useFilterMetaModel<number>(filters, 'creator_id')
const changedRange = useDateRangeFilter(changedFrom, changedTo)
const changedById = useFilterMetaModel<number>(filters, 'changed_by_id')
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const canWrite = computed(() => hasPermission(Permission.WRITE_SUPPLIERS))
const canDelete = computed(() => hasPermission(Permission.DELETE_SUPPLIERS))

const editDialogVisible = ref(false)
const editingSupplier = ref<SupplierResponse | undefined>(undefined)

function onEditSupplier(supplier: SupplierResponse): void {
  editingSupplier.value = supplier
  editDialogVisible.value = true
}

function onSaved(supplier: SupplierResponse): void {
  toast.success(supplier.name, t('resources.suppliers.editSupplier'))
}

// Context menu, archive confirm and row opening come from
// useManagementResourceActions.
const {
  cm,
  contextMenuTarget: contextMenuItem,
  detailDialogVisible,
  detailTarget: detailSupplier,
  contextMenuItems,
  onRowContextMenu,
  onRowClick,
  onDelete: onArchiveSupplier,
  onRestore: onRestoreSupplier,
} = useManagementResourceActions<SupplierResponse>(store, {
  i18nPrefix: 'resources.suppliers',
  entityLabel: (supplier) => supplier.name,
  deletePermission: Permission.DELETE_SUPPLIERS,
  archivable: { isArchived: (supplier) => supplier.archived },
  editItem: (supplier) => ({
    label: t('resources.suppliers.editSupplier'),
    icon: 'mdi mdi-pencil',
    disabled: !canWrite.value,
    command: () => onEditSupplier(supplier),
  }),
})

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: ({ first, rows }) => ({ skip: first, limit: rows }),
  fetch: (params) => store.refreshTable(params),
})

useFilterMetaWatch(
  filters,
  ['name', 'legal_name', 'address', 'country', 'email'],
  resetAndFetchDebounced,
)
useFilterMetaWatch(
  filters,
  ['level', 'capability_id', 'article_group_id', 'creator_id', 'changed_by_id'],
  resetAndFetch,
)
watch([createdFrom, createdTo, changedFrom, changedTo], resetAndFetch)
watch(search, resetAndFetchDebounced)
watch(showArchived, resetAndFetch)

watch(clearTrigger, () => {
  resetAndFetch()
})

watch([sortBy, sortDir], () => {
  resetAndFetch()
})

watch(
  () => store.refreshTrigger,
  () => fetchItems(),
)

onMounted(() => {
  void usersStore.ensureLoaded()
  if (!fabricationMethodsStore.items.length) void fabricationMethodsStore.refresh()
  if (!articleGroupsStore.items.length) void articleGroupsStore.refresh()
})

const groupedItems = computed(() => {
  if (!groupBy.value) return items.value

  if (groupBy.value === 'capability') {
    return groupRowsByLabel(
      items.value,
      '_capabilityGroup',
      (item) => localizeLabel(item.capabilities[0]?.name) || getEmptyPlaceholder(),
    )
  }

  return groupRowsByLabel(items.value, '_countryGroup', (item) => item.country ?? getEmptyPlaceholder())
})

const groupRowsBy = computed(() => {
  if (!groupBy.value) return undefined
  return groupBy.value === 'capability' ? '_capabilityGroup' : '_countryGroup'
})

// Server-side sort. The controlled sortField and sortOrder keep the header
// icon in step with the view's sort control.
function onSort(event: DataTableSortEvent): void {
  if (typeof event.sortField === 'string' && event.sortOrder) {
    store.setSort(event.sortField as SupplierSortBy, event.sortOrder === 1 ? 'asc' : 'desc')
  } else {
    store.clearSort()
  }
}

const detailFields = computed(() => {
  const s = detailSupplier.value
  if (!s) return []
  const address = formatAddress(s)
  return [
    { label: t('resources.suppliers.fields.name'), value: s.name },
    { label: t('resources.suppliers.fields.legalName'), value: s.legal_name },
    { label: t('resources.suppliers.fields.vatId'), value: s.vat_id },
    { label: t('resources.suppliers.fields.level'), value: s.level },
    { label: t('resources.suppliers.columns.address'), value: address || null },
    { label: t('resources.suppliers.fields.country'), value: s.country },
    { label: t('resources.suppliers.fields.email'), value: s.email },
    { label: t('resources.suppliers.fields.phone'), value: s.phone },
    { label: t('resources.suppliers.fields.weblink'), value: s.weblink },
    { label: t('resources.suppliers.fields.orderEmail'), value: s.order_email },
    { label: t('resources.suppliers.fields.orderLanguage'), value: s.order_language },
    {
      label: t('resources.suppliers.columns.capabilities'),
      value: s.capabilities.map((c) => localizeLabel(c.name)).join(', ') || null,
    },
    {
      label: t('resources.suppliers.columns.articleGroups'),
      value: s.article_groups.map((g) => localizeLabel(g.name)).join(', ') || null,
    },
    { label: t('resources.suppliers.columns.creator'), value: s.creator?.full_name ?? null },
    { label: t('resources.suppliers.columns.created'), value: formatDate(s.created) },
    {
      label: t('resources.suppliers.columns.changed'),
      value: s.changed ? formatDate(s.changed) : null,
    },
  ]
})
</script>

<template>
  <DataTable
    :value="groupedItems"
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
    :sort-field="sortBy ?? undefined"
    :sort-order="sortBy ? (sortDir === 'asc' ? 1 : -1) : undefined"
    removable-sort
    @sort="onSort"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    scrollable
    scroll-height="flex"
    resizable-columns
    column-resize-mode="fit"
    :row-group-mode="groupBy ? 'subheader' : undefined"
    :group-rows-by="groupRowsBy"
    class="phone-columns suppliers-table suppliers-rows-clickable"
    @row-contextmenu="onRowContextMenu"
    selection-mode="single"
    @row-click="onRowClick"
    @row-select="onRowClick"
  >
    <template v-if="groupBy" #groupheader="{ data }">
      <div class="group-header">
        <i v-if="groupBy === 'capability'" class="mdi mdi-wrench-outline" aria-hidden="true" />
        <i v-else class="mdi mdi-earth" aria-hidden="true" />
        <span class="group-header-label">{{
          groupBy === 'capability' ? data._capabilityGroup : data._countryGroup
        }}</span>
      </div>
    </template>
    <template #empty>
      <EmptyState />
    </template>

    <Column header="#" header-style="width: 3rem" body-class="row-number" class="phone-row-number">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>
    <Column
      v-if="store.showActions"
      :header="t('resources.suppliers.columns.actions')"
      style="width: 6rem"
    >
      <template #body="{ data }: { data: SupplierResponse }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            :disabled="!canWrite"
            v-tooltip.top.focus="t('resources.suppliers.editSupplier')"
            :aria-label="t('resources.suppliers.editSupplier')"
            @click.stop="onEditSupplier(data)"
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
            @click.stop="onArchiveSupplier(data)"
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
            @click.stop="onRestoreSupplier(data)"
          />
        </div>
      </template>
    </Column>

    <Column
      class="phone-col"
      field="name"
      :header="t('resources.suppliers.columns.name')"
      :show-filter-menu="false"
      sortable
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.suppliers.filters.name')"
          :aria-label="t('common.filterBy', { column: t('resources.suppliers.columns.name') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="legal_name"
      :header="t('resources.suppliers.columns.legalName')"
      :show-filter-menu="false"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.suppliers.filters.legalName')"
          :aria-label="t('common.filterBy', { column: t('resources.suppliers.columns.legalName') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="level"
      :header="t('resources.suppliers.columns.level')"
      :show-filter-menu="false"
      style="width: 6rem"
    >
      <template #body="{ data }: { data: SupplierResponse }">
        <Tag
          v-if="data.level"
          :value="data.level"
          :severity="data.level === 'A' ? 'success' : data.level === 'B' ? 'info' : 'danger'"
        />
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="levelOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('resources.suppliers.filters.any')"
          :aria-label="t('common.filterBy', { column: t('resources.suppliers.columns.level') })"
          show-clear
          size="small"
          fluid
          @change="filterCallback()"
        />
      </template>
    </Column>

    <Column :header="t('common.archivedTag')" style="width: 7rem">
      <template #body="{ data }: { data: SupplierResponse }">
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
      filter-field="capability_id"
      :header="t('resources.suppliers.columns.capabilities')"
      :show-filter-menu="false"
      style="width: 14rem"
    >
      <template #body="{ data }: { data: SupplierResponse }">
        <div v-if="data.capabilities.length" class="tag-list">
          <LabelTag
            v-for="cap in data.capabilities"
            :key="cap.id"
            :label="cap"
          />
        </div>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="capabilityFilterOptions"
          :option-label="labelName"
          option-value="id"
          :placeholder="t('resources.suppliers.filters.any')"
          :aria-label="t('common.filterBy', { column: t('resources.suppliers.columns.capabilities') })"
          show-clear
          filter
          size="small"
          fluid
          @change="filterCallback()"
        >
          <template #option="{ option }">
            <span>{{ localizeLabel(option.name) }}</span>
            <ArchivedOptionTag v-if="option.archived" />
          </template>
        </Select>
      </template>
    </Column>

    <Column
      filter-field="article_group_id"
      :header="t('resources.suppliers.columns.articleGroups')"
      :show-filter-menu="false"
      style="width: 14rem"
    >
      <template #body="{ data }: { data: SupplierResponse }">
        <div v-if="data.article_groups.length" class="tag-list">
          <LabelTag
            v-for="group in data.article_groups"
            :key="group.id"
            :label="group"
          />
        </div>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="articleGroupFilterOptions"
          :option-label="labelName"
          option-value="id"
          :placeholder="t('resources.suppliers.filters.any')"
          :aria-label="t('common.filterBy', { column: t('resources.suppliers.columns.articleGroups') })"
          show-clear
          filter
          size="small"
          fluid
          @change="filterCallback()"
        >
          <template #option="{ option }">
            <span>{{ localizeLabel(option.name) }}</span>
            <ArchivedOptionTag v-if="option.archived" />
          </template>
        </Select>
      </template>
    </Column>

    <Column
      :header="t('resources.suppliers.columns.address')"
      field="street"
      filter-field="address"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: SupplierResponse }">
        <span>{{ formatAddress(data) }}</span>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.suppliers.filters.address')"
          :aria-label="t('common.filterBy', { column: t('resources.suppliers.columns.address') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="country"
      :header="t('resources.suppliers.columns.country')"
      :show-filter-menu="false"
      style="width: 9rem"
    >
      <template #body="{ data }: { data: SupplierResponse }">
        <span v-if="data.country">{{ data.country }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.suppliers.filters.country')"
          :aria-label="t('common.filterBy', { column: t('resources.suppliers.columns.country') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      class="phone-col"
      field="email"
      :header="t('resources.suppliers.columns.email')"
      :show-filter-menu="false"
      style="width: 12rem"
    >
      <template #body="{ data }: { data: SupplierResponse }">
        <ContactLinks :email="data.email" />
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.suppliers.filters.email')"
          :aria-label="t('common.filterBy', { column: t('resources.suppliers.columns.email') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="created"
      :header="t('resources.suppliers.columns.created')"
      :show-filter-menu="false"
      sortable
      style="width: 10rem"
    >
      <template #body="{ data }: { data: SupplierResponse }">
        <UserDateCell :date="data.created" :user="data.creator" />
      </template>
      <template #filter>
        <UserDateFilter
          v-model:user-id="creatorId"
          v-model:range="createdRange"
          :column="t('resources.suppliers.columns.created')"
          :placeholder="t('resources.suppliers.filters.any')"
        />
      </template>
    </Column>

    <Column
      field="changed"
      :header="t('resources.suppliers.columns.changed')"
      :show-filter-menu="false"
      style="width: 10rem"
    >
      <template #body="{ data }: { data: SupplierResponse }">
        <UserDateCell :date="data.changed" :user="data.changed_by" />
      </template>
      <template #filter>
        <UserDateFilter
          v-model:user-id="changedById"
          v-model:range="changedRange"
          :column="t('resources.suppliers.columns.changed')"
          :placeholder="t('resources.suppliers.filters.any')"
        />
      </template>
    </Column>

    <Column style="width: 100%" />
  </DataTable>

  <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />

  <SupplierFormDialog
    v-model:visible="editDialogVisible"
    :supplier="editingSupplier"
    @saved="onSaved"
  />

  <ResourceDetailDialog
    v-model:visible="detailDialogVisible"
    :title="t('resources.suppliers.showDetails')"
    :fields="detailFields"
  />
</template>

<style scoped lang="scss">
.suppliers-table {
  width: 100%;
}

.suppliers-rows-clickable {
  :deep(.p-datatable-tbody) > tr {
    cursor: pointer;
  }
}

.group-header-label {
  font-weight: bold;
  padding-left: var(--space-4);
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}


.level-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  background: var(--p-primary-100);
  color: var(--p-primary-700);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.p-dark .level-badge {
  background: var(--p-primary-900);
  color: var(--p-primary-200);
}
</style>
