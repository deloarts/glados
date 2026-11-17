<script setup lang="ts">
import { onMounted, ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAppToast } from '@/core/composables/useAppToast'
import { storeToRefs } from 'pinia'
import type { DataTableSortEvent } from 'openvue/datatable'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useServerTable } from '@/core/composables/useServerTable'
import { useManagementResourceActions } from '@/shared/composables/useManagementResourceActions'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { useFilterMetaModel } from '@/shared/composables/useFilterMetaModel'
import { useFilterMetaWatch } from '@/shared/composables/useFilterMetaWatch'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import EmptyState from '@/shared/components/EmptyState.vue'

import { useProductsStore } from '../stores/productsStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import ProductFormDialog from './ProductFormDialog.vue'
import ProductThumbnailCell from './ProductThumbnailCell.vue'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'
import { useUsersStore } from '@/core/stores/usersStore'
import { useCustomersStore } from '@/features/customers'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import type { ProductResponse } from '../types/productResponse'
import type { ProductSortBy } from '../types/productRequest'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { groupRowsByLabel } from '@/core/utils/tableRowGrouping'

const { t } = useI18n()
const router = useRouter()
const toast = useAppToast()

const store = useProductsStore()
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
} = storeToRefs(store)
watchLoadingBar(loading)
const createdRange = useDateRangeFilter(createdFrom, createdTo)
const creatorId = useFilterMetaModel<number>(filters, 'creator_id')
const usersStore = useUsersStore()
const customersStore = useCustomersStore()
const hostStore = useHostStore()
const currentUserStore = useCurrentUserStore()
const { hasPermission } = usePermissions()

// Archived customers stay selectable in the filter, sorted last.
const { sortedOptions: customerFilterOptions } = useArchivableOptions(
  computed(() => customersStore.items),
)
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const canManage = computed(() => hasPermission(Permission.MANAGE_PROJECTS))
const canWrite = computed(() => hasPermission(Permission.WRITE_PROJECTS))

const activeOptions = [
  { label: t('resources.products.filters.active'), value: true },
  { label: t('resources.products.filters.inactive'), value: false },
]

const editDialogVisible = ref(false)
const editingProduct = ref<ProductResponse | undefined>(undefined)

function canEdit(product: ProductResponse): boolean {
  return (
    canManage.value || (canWrite.value && product.designated_user_id === currentUserStore.user?.id)
  )
}

// A row action the user lacks the rights for stays visible and disabled, and
// its tooltip says why: the missing permission, or for edit that only the
// designated user may edit without Manage Projects.
const { missing } = useMissingPermission()

function editTooltip(product: ProductResponse): string {
  if (canEdit(product)) return t('resources.products.editProduct')
  if (!canWrite.value) return missing(Permission.WRITE_PROJECTS)
  return t('resources.products.detail.editDesignatedOnly')
}

const archiveTooltip = computed(() => missing(Permission.MANAGE_PROJECTS) || t('common.archive'))
const restoreTooltip = computed(() => missing(Permission.MANAGE_PROJECTS) || t('common.restore'))

function onEditProduct(product: ProductResponse): void {
  editingProduct.value = product
  editDialogVisible.value = true
}

function onSaved(product: ProductResponse): void {
  toast.success(product.product_number, t('resources.products.editProduct'))
}

// Context menu, archive confirm and row opening come from
// useManagementResourceActions, as on the projects table. Show details and a
// row click open the product page. Archive needs manage:projects, since
// products live under the projects permission.
const {
  cm,
  contextMenuTarget: contextMenuItem,
  contextMenuItems,
  onRowContextMenu,
  onRowClick,
  onDelete: onArchiveProduct,
  onRestore: onRestoreProduct,
} = useManagementResourceActions<ProductResponse>(store, {
  i18nPrefix: 'resources.products',
  entityLabel: (product) => product.product_number,
  deletePermission: Permission.MANAGE_PROJECTS,
  archivable: { isArchived: (product) => product.archived },
  editItem: (product) => ({
    label: t('resources.products.editProduct'),
    icon: 'mdi mdi-pencil',
    disabled: !canEdit(product),
    title: canEdit(product) ? undefined : editTooltip(product),
    command: () => onEditProduct(product),
  }),
  onShowDetail: (product) => void router.push(`/workspace/products/${product.id}`),
})

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: ({ first, rows }) => ({ skip: first, limit: rows }),
  fetch: (params) => store.refreshTable(params),
})

useFilterMetaWatch(filters, ['product_number', 'description'], resetAndFetchDebounced)
useFilterMetaWatch(
  filters,
  ['is_active', 'customer_id', 'designated_user_id', 'creator_id'],
  resetAndFetch,
)
watch([createdFrom, createdTo], resetAndFetch)
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

const groupedItems = computed(() => {
  if (!groupBy.value) return items.value

  if (groupBy.value === 'is_active') {
    return groupRowsByLabel(
      items.value,
      '_activeGroup',
      (item) =>
        item.is_active ? t('resources.products.filters.active') : t('resources.products.filters.inactive'),
    )
  }

  return groupRowsByLabel(
    items.value,
    '_customerGroup',
    (item) => item.customer?.name ?? getEmptyPlaceholder(),
  )
})

const groupRowsBy = computed(() => {
  if (!groupBy.value) return undefined
  return groupBy.value === 'is_active' ? '_activeGroup' : '_customerGroup'
})

onMounted(() => {
  void usersStore.ensureLoaded()
  if (!customersStore.items.length) void customersStore.refresh()
})

// Server-side sort. The controlled sortField and sortOrder keep the header
// icon in step with the view's sort control.
function onSort(event: DataTableSortEvent): void {
  if (typeof event.sortField === 'string' && event.sortOrder) {
    store.setSort(event.sortField as ProductSortBy, event.sortOrder === 1 ? 'asc' : 'desc')
  } else {
    store.clearSort()
  }
}
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
    class="products-table clickable-rows"
    @row-contextmenu="onRowContextMenu"
    selection-mode="single"
    @row-click="onRowClick"
    @row-select="onRowClick"
  >
    <template v-if="groupBy" #groupheader="{ data }">
      <div class="group-header">
        <i v-if="groupBy === 'is_active'" class="mdi mdi-check-circle-outline" aria-hidden="true" />
        <i v-else class="mdi mdi-domain" aria-hidden="true" />
        <span class="group-header-label">{{
          groupBy === 'is_active' ? data._activeGroup : data._customerGroup
        }}</span>
      </div>
    </template>

    <template #empty>
      <EmptyState />
    </template>

    <Column
      v-if="store.showActions"
      :header="t('resources.products.columns.actions')"
      style="width: 6rem"
    >
      <template #body="{ data }: { data: ProductResponse }">
        <div class="row-actions">
          <span v-tooltip.top="editTooltip(data)">
            <Button
              icon="mdi mdi-pencil"
              size="small"
              severity="secondary"
              text
              :disabled="!canEdit(data)"
              :aria-label="t('resources.products.editProduct')"
              @click.stop="onEditProduct(data)"
            />
          </span>
          <span v-if="!data.archived" v-tooltip.top="archiveTooltip">
            <Button
              icon="mdi mdi-archive-outline"
              size="small"
              severity="danger"
              text
              :disabled="!canManage"
              :aria-label="t('common.archive')"
              @click.stop="onArchiveProduct(data)"
            />
          </span>
          <span v-else v-tooltip.top="restoreTooltip">
            <Button
              icon="mdi mdi-archive-arrow-up-outline"
              size="small"
              severity="secondary"
              text
              :disabled="!canManage"
              :aria-label="t('common.restore')"
              @click.stop="onRestoreProduct(data)"
            />
          </span>
        </div>
      </template>
    </Column>

    <Column
      v-if="hostStore.storageEnabled"
      :header="t('resources.products.columns.image')"
      style="width: 3.25rem; min-width: 3.25rem; padding: var(--space-1) var(--space-2)"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: ProductResponse }">
        <ProductThumbnailCell :item-id="data.id" :item-name="data.product_number" />
      </template>
    </Column>

    <Column
      field="is_active"
      :header="t('resources.products.columns.active')"
      :show-filter-menu="false"
      style="width: 8rem"
    >
      <template #body="{ data }: { data: ProductResponse }">
        <Tag
          :value="
            data.is_active
              ? t('resources.products.filters.active')
              : t('resources.products.filters.inactive')
          "
          :severity="data.is_active ? 'success' : 'danger'"
        />
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="activeOptions"
          option-label="label"
          option-value="value"
          show-clear
          :aria-label="t('common.filterBy', { column: t('resources.products.columns.active') })"
          size="small"
          fluid
          @change="filterCallback()"
        />
      </template>
    </Column>

    <Column :header="t('common.archivedTag')" style="width: 7rem">
      <template #body="{ data }: { data: ProductResponse }">
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
      field="product_number"
      :header="t('resources.products.columns.productNumber')"
      :show-filter-menu="false"
      sortable
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.products.filters.productNumber')"
          :aria-label="t('common.filterBy', { column: t('resources.products.columns.productNumber') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="customer_id"
      :header="t('resources.products.columns.customer')"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: ProductResponse }">
        <span v-if="data.customer">{{ data.customer.name }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="customerFilterOptions"
          option-label="name"
          option-value="id"
          :placeholder="t('resources.products.filters.customer')"
          :aria-label="t('common.filterBy', { column: t('resources.products.columns.customer') })"
          show-clear
          filter
          size="small"
          fluid
          @change="filterCallback()"
        >
          <template #option="{ option }">
            <span>{{ option.name }}</span>
            <ArchivedOptionTag v-if="option.archived" />
          </template>
        </Select>
      </template>
    </Column>

    <Column
      field="description"
      :header="t('resources.products.columns.description')"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: ProductResponse }">
        <span v-if="data.description">{{ data.description }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.products.filters.description')"
          :aria-label="t('common.filterBy', { column: t('resources.products.columns.description') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="designated_user_id"
      :header="t('resources.products.columns.designatedUser')"
      :show-filter-menu="false"
      style="width: 10rem"
    >
      <template #body="{ data }: { data: ProductResponse }">
        <UserAvatarPreview :user="usersStore.getById(data.designated_user_id) ?? null" />
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="usersStore.users"
          option-label="full_name"
          option-value="id"
          :loading="usersStore.loading"
          :placeholder="t('resources.products.filters.any')"
          :aria-label="t('common.filterBy', { column: t('resources.products.columns.designatedUser') })"
          show-clear
          filter
          size="small"
          fluid
          @change="filterCallback()"
        />
      </template>
    </Column>

    <Column
      field="created"
      :header="t('resources.products.columns.created')"
      :show-filter-menu="false"
      sortable
      style="width: 10rem"
    >
      <template #body="{ data }: { data: ProductResponse }">
        <UserDateCell :date="data.created" :user="data.creator" />
      </template>
      <template #filter>
        <UserDateFilter
          v-model:user-id="creatorId"
          v-model:range="createdRange"
          :column="t('resources.products.columns.created')"
          :placeholder="t('resources.products.filters.any')"
        />
      </template>
    </Column>

    <Column style="width: 100%" />
  </DataTable>

  <ContextMenu
    ref="cm"
    :model="contextMenuItems"
    :pt="disabledItemTooltipPt"
    @hide="contextMenuItem = null"
  />

  <ProductFormDialog
    v-model:visible="editDialogVisible"
    :product="editingProduct"
    @saved="onSaved"
  />
</template>

<style scoped lang="scss">
.products-table {
  width: 100%;
}

.group-header-label {
  font-weight: bold;
  padding-left: var(--space-4);
}
</style>
