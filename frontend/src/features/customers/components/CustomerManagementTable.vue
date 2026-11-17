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
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { useFilterMetaModel } from '@/shared/composables/useFilterMetaModel'
import { useFilterMetaWatch } from '@/shared/composables/useFilterMetaWatch'
import { useUsersStore } from '@/core/stores/usersStore'

import { useCustomersStore } from '../stores/customersStore'
import CustomerFormDialog from './CustomerFormDialog.vue'
import ResourceDetailDialog from '@/shared/components/dialogs/ResourceDetailDialog.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import type { CustomerResponse } from '../types/customerResponse'
import type { CustomerSortBy } from '../types/customerRequest'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ContactLinks from '@/shared/components/ContactLinks.vue'
import { groupRowsByLabel } from '@/core/utils/tableRowGrouping'

const { t } = useI18n()
const toast = useAppToast()

const store = useCustomersStore()
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
const levelOptions = ['A', 'B', 'C'].map((level) => ({ label: level, value: level }))
const createdRange = useDateRangeFilter(createdFrom, createdTo)
const creatorId = useFilterMetaModel<number>(filters, 'creator_id')
const changedRange = useDateRangeFilter(changedFrom, changedTo)
const changedById = useFilterMetaModel<number>(filters, 'changed_by_id')
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const canWrite = computed(() => hasPermission(Permission.WRITE_PROJECTS))
const canManage = computed(() => hasPermission(Permission.MANAGE_PROJECTS))

const editDialogVisible = ref(false)
const editingCustomer = ref<CustomerResponse | undefined>(undefined)

function onEditCustomer(customer: CustomerResponse): void {
  editingCustomer.value = customer
  editDialogVisible.value = true
}

function onSaved(customer: CustomerResponse): void {
  toast.success(customer.name, t('resources.customers.editCustomer'))
}

// Context menu, archive confirm and row opening come from
// useManagementResourceActions.
const {
  cm,
  contextMenuTarget: contextMenuItem,
  detailDialogVisible,
  detailTarget: detailCustomer,
  contextMenuItems,
  onRowContextMenu,
  onRowClick,
  onDelete: onArchiveCustomer,
  onRestore: onRestoreCustomer,
} = useManagementResourceActions<CustomerResponse>(store, {
  i18nPrefix: 'resources.customers',
  entityLabel: (customer) => customer.name,
  deletePermission: Permission.MANAGE_PROJECTS,
  archivable: { isArchived: (customer) => customer.archived },
  editItem: (customer) => ({
    label: t('resources.customers.editCustomer'),
    icon: 'mdi mdi-pencil',
    disabled: !canWrite.value,
    command: () => onEditCustomer(customer),
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
useFilterMetaWatch(filters, ['level', 'creator_id', 'changed_by_id'], resetAndFetch)
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
})

const groupedItems = computed(() => {
  if (!groupBy.value) return items.value

  if (groupBy.value === 'level') {
    return groupRowsByLabel(items.value, '_levelGroup', (item) => item.level)
  }

  return groupRowsByLabel(items.value, '_countryGroup', (item) => item.country ?? getEmptyPlaceholder())
})

const groupRowsBy = computed(() => {
  if (!groupBy.value) return undefined
  return groupBy.value === 'level' ? '_levelGroup' : '_countryGroup'
})

// Server-side sort. The controlled sortField and sortOrder keep the header
// icon in step with the view's sort control.
function onSort(event: DataTableSortEvent): void {
  if (typeof event.sortField === 'string' && event.sortOrder) {
    store.setSort(event.sortField as CustomerSortBy, event.sortOrder === 1 ? 'asc' : 'desc')
  } else {
    store.clearSort()
  }
}

const detailFields = computed(() => {
  const c = detailCustomer.value
  if (!c) return []
  const address = formatAddress(c)
  return [
    { label: t('resources.customers.fields.name'), value: c.name },
    { label: t('resources.customers.fields.legalName'), value: c.legal_name },
    { label: t('resources.customers.fields.vatId'), value: c.vat_id },
    { label: t('resources.customers.fields.level'), value: c.level },
    { label: t('resources.customers.columns.address'), value: address || null },
    { label: t('resources.customers.fields.country'), value: c.country },
    { label: t('resources.customers.fields.email'), value: c.email },
    { label: t('resources.customers.fields.phone'), value: c.phone },
    { label: t('resources.customers.fields.weblink'), value: c.weblink },
    { label: t('resources.customers.columns.creator'), value: c.creator?.full_name ?? null },
    { label: t('resources.customers.columns.created'), value: formatDate(c.created) },
    {
      label: t('resources.customers.columns.changed'),
      value: c.changed ? formatDate(c.changed) : null,
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
    class="phone-columns customers-table clickable-rows"
    @row-contextmenu="onRowContextMenu"
    selection-mode="single"
    @row-click="onRowClick"
    @row-select="onRowClick"
  >
    <template v-if="groupBy" #groupheader="{ data }">
      <div class="group-header">
        <i v-if="groupBy === 'level'" class="mdi mdi-star-outline" aria-hidden="true" />
        <i v-else class="mdi mdi-earth" aria-hidden="true" />
        <span class="group-header-label">{{
          groupBy === 'level' ? data._levelGroup : data._countryGroup
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
      :header="t('resources.customers.columns.actions')"
      style="width: 6rem"
    >
      <template #body="{ data }: { data: CustomerResponse }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            :disabled="!canWrite"
            v-tooltip.top.focus="t('resources.customers.editCustomer')"
            :aria-label="t('resources.customers.editCustomer')"
            @click.stop="onEditCustomer(data)"
          />
          <Button
            v-if="!data.archived"
            icon="mdi mdi-archive-outline"
            size="small"
            severity="danger"
            text
            :disabled="!canManage"
            v-tooltip.top.focus="t('common.archive')"
            :aria-label="t('common.archive')"
            @click.stop="onArchiveCustomer(data)"
          />
          <Button
            v-else
            icon="mdi mdi-archive-arrow-up-outline"
            size="small"
            severity="secondary"
            text
            :disabled="!canManage"
            v-tooltip.top.focus="t('common.restore')"
            :aria-label="t('common.restore')"
            @click.stop="onRestoreCustomer(data)"
          />
        </div>
      </template>
    </Column>

    <Column
      class="phone-col"
      field="name"
      :header="t('resources.customers.columns.name')"
      :show-filter-menu="false"
      sortable
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.customers.filters.name')"
          :aria-label="t('common.filterBy', { column: t('resources.customers.columns.name') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="legal_name"
      :header="t('resources.customers.columns.legalName')"
      :show-filter-menu="false"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.customers.filters.legalName')"
          :aria-label="t('common.filterBy', { column: t('resources.customers.columns.legalName') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="level"
      :header="t('resources.customers.columns.level')"
      :show-filter-menu="false"
      style="width: 6rem"
    >
      <template #body="{ data }: { data: CustomerResponse }">
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
          :placeholder="t('resources.customers.filters.any')"
          :aria-label="t('common.filterBy', { column: t('resources.customers.columns.level') })"
          show-clear
          size="small"
          fluid
          @change="filterCallback()"
        />
      </template>
    </Column>

    <Column :header="t('common.archivedTag')" style="width: 7rem">
      <template #body="{ data }: { data: CustomerResponse }">
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
      :header="t('resources.customers.columns.address')"
      field="street"
      filter-field="address"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: CustomerResponse }">
        <span>{{ formatAddress(data) }}</span>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.customers.filters.address')"
          :aria-label="t('common.filterBy', { column: t('resources.customers.columns.address') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="country"
      :header="t('resources.customers.columns.country')"
      :show-filter-menu="false"
      style="width: 9rem"
    >
      <template #body="{ data }: { data: CustomerResponse }">
        <span v-if="data.country">{{ data.country }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.customers.filters.country')"
          :aria-label="t('common.filterBy', { column: t('resources.customers.columns.country') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      class="phone-col"
      field="email"
      :header="t('resources.customers.columns.email')"
      :show-filter-menu="false"
      style="width: 12rem"
    >
      <template #body="{ data }: { data: CustomerResponse }">
        <ContactLinks :email="data.email" :phone="data.phone" />
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.customers.filters.email')"
          :aria-label="t('common.filterBy', { column: t('resources.customers.columns.email') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="created"
      :header="t('resources.customers.columns.created')"
      :show-filter-menu="false"
      sortable
      style="width: 10rem"
    >
      <template #body="{ data }: { data: CustomerResponse }">
        <UserDateCell :date="data.created" :user="data.creator" />
      </template>
      <template #filter>
        <UserDateFilter
          v-model:user-id="creatorId"
          v-model:range="createdRange"
          :column="t('resources.customers.columns.created')"
          :placeholder="t('resources.customers.filters.any')"
        />
      </template>
    </Column>

    <Column
      field="changed"
      :header="t('resources.customers.columns.changed')"
      :show-filter-menu="false"
      sortable
      style="width: 10rem"
    >
      <template #body="{ data }: { data: CustomerResponse }">
        <UserDateCell :date="data.changed" :user="data.changed_by" />
      </template>
      <template #filter>
        <UserDateFilter
          v-model:user-id="changedById"
          v-model:range="changedRange"
          :column="t('resources.customers.columns.changed')"
          :placeholder="t('resources.customers.filters.any')"
        />
      </template>
    </Column>

    <Column style="width: 100%" />
  </DataTable>

  <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />

  <CustomerFormDialog
    v-model:visible="editDialogVisible"
    :customer="editingCustomer"
    @saved="onSaved"
  />

  <ResourceDetailDialog
    v-model:visible="detailDialogVisible"
    :title="t('resources.customers.showDetails')"
    :fields="detailFields"
  />
</template>

<style scoped lang="scss">
.customers-table {
  width: 100%;
}

.group-header-label {
  font-weight: bold;
  padding-left: var(--space-4);
}
</style>
