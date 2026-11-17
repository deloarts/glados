<script setup lang="ts">
import { onMounted, ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAppToast } from '@/core/composables/useAppToast'
import { storeToRefs } from 'pinia'
import type { DataTableSortEvent } from 'openvue/datatable'
import { formatDateOrDash } from '@/core/utils/dates'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useServerTable } from '@/core/composables/useServerTable'
import { useManagementResourceActions } from '@/shared/composables/useManagementResourceActions'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { useFilterMetaModel } from '@/shared/composables/useFilterMetaModel'
import { useFilterMetaWatch } from '@/shared/composables/useFilterMetaWatch'
import DemandDateRangeFilter from '@/shared/components/demands/DemandDateRangeFilter.vue'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import EmptyState from '@/shared/components/EmptyState.vue'

import { useProjectsStore } from '../stores/projectsStore'
import { useProjectMoveReasons } from '../composables/useProjectMoveReasons'
import ProjectFormDialog from './ProjectFormDialog.vue'
import ProjectItemsDialog from './ProjectItemsDialog.vue'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'
import { useUsersStore } from '@/core/stores/usersStore'
import { useCustomersStore } from '@/features/customers'
import { useProductsStore } from '@/features/products'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import { PROJECT_STATUSES, projectStatusSeverity } from '../utils/projectStatus'
import type { ProjectResponse } from '../types/projectResponse'
import type { ProjectSortBy } from '../types/projectRequest'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { groupRowsByLabel } from '@/core/utils/tableRowGrouping'

const { t } = useI18n()
const router = useRouter()
const toast = useAppToast()

const store = useProjectsStore()
const {
  tableItems: items,
  loading,
  filters,
  clearTrigger,
  search,
  sortBy,
  sortDir,
  groupBy,
  createdFrom,
  createdTo,
  deliveryMadeFrom,
  deliveryMadeTo,
  deliveryBoughtFrom,
  deliveryBoughtTo,
} = storeToRefs(store)
watchLoadingBar(loading)
const usersStore = useUsersStore()
const customersStore = useCustomersStore()
const productsStore = useProductsStore()
const createdRange = useDateRangeFilter(createdFrom, createdTo)
const creatorId = useFilterMetaModel<number>(filters, 'creator_id')
const deliveryMadeRange = useDateRangeFilter(deliveryMadeFrom, deliveryMadeTo)
const deliveryBoughtRange = useDateRangeFilter(deliveryBoughtFrom, deliveryBoughtTo)
const currentUserStore = useCurrentUserStore()
const { hasPermission } = usePermissions()

// Archived customers stay selectable in the filter, sorted last.
const { sortedOptions: customerFilterOptions } = useArchivableOptions(
  computed(() => customersStore.items),
)
const { sortedOptions: productFilterOptions } = useArchivableOptions(
  computed(() => productsStore.items),
)
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const canManage = computed(() => hasPermission(Permission.MANAGE_PROJECTS))
const canWrite = computed(() => hasPermission(Permission.WRITE_PROJECTS))

const statusOptions = PROJECT_STATUSES.map((s) => ({
  label: t(`resources.projects.status.${s}`),
  value: s,
}))

const editDialogVisible = ref(false)
const editingProject = ref<ProjectResponse | undefined>(undefined)

const itemsDialogVisible = ref(false)
const itemsDialogProject = ref<ProjectResponse | null>(null)

function onEditProject(project: ProjectResponse): void {
  editingProject.value = project
  editDialogVisible.value = true
}

function onSaved(project: ProjectResponse): void {
  toast.success(project.project_number, t('resources.projects.editProject'))
}

function onShowItems(project: ProjectResponse): void {
  itemsDialogProject.value = project
  itemsDialogVisible.value = true
}

function canEdit(project: ProjectResponse): boolean {
  return (
    canManage.value || (canWrite.value && project.designated_user_id === currentUserStore.user?.id)
  )
}

const { deleteBlockedReason, deleteTooltip } = useProjectMoveReasons()

// A disabled edit button says why: the missing permission, or that only the
// designated user may edit without Manage Projects.
const { missing } = useMissingPermission()

function editTooltip(project: ProjectResponse): string {
  if (canEdit(project)) return t('resources.projects.editProject')
  if (!canWrite.value) return missing(Permission.WRITE_PROJECTS)
  return t('resources.projects.detail.editDesignatedOnly')
}

// Context menu, delete confirm and row opening come from the shared
// composable. Show details routes to the project page, and extraItems adds
// "Show items". Delete needs manage:projects and a project without live work.
const {
  cm,
  contextMenuTarget: contextMenuItem,
  contextMenuItems,
  onRowContextMenu,
  onRowClick,
  onDelete: onDeleteProject,
} = useManagementResourceActions<ProjectResponse>(store, {
  i18nPrefix: 'resources.projects',
  entityLabel: (project) => project.project_number,
  deletePermission: Permission.MANAGE_PROJECTS,
  deleteBlocked: (project) => deleteBlockedReason(project) !== null,
  deleteConfirmParams: (project) => ({ number: project.project_number }),
  editItem: (project) => ({
    label: t('resources.projects.editProject'),
    icon: 'mdi mdi-pencil',
    disabled: !canEdit(project),
    title: canEdit(project) ? undefined : editTooltip(project),
    command: () => onEditProject(project),
  }),
  onShowDetail: (project) => void router.push(`/workspace/projects/${project.id}`),
  extraItems: (project) => [
    {
      label: t('resources.projects.showItems'),
      icon: 'mdi mdi-package-variant-closed',
      command: () => onShowItems(project),
    },
  ],
})

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: ({ first, rows }) => ({ skip: first, limit: rows }),
  fetch: (params) => store.refreshTable(params),
})

useFilterMetaWatch(filters, ['project_number', 'description'], resetAndFetchDebounced)
useFilterMetaWatch(
  filters,
  ['status', 'customer_id', 'product_id', 'designated_user_id', 'creator_id'],
  resetAndFetch,
)
watch(
  [createdFrom, createdTo, deliveryMadeFrom, deliveryMadeTo, deliveryBoughtFrom, deliveryBoughtTo],
  resetAndFetch,
)
watch(search, resetAndFetchDebounced)

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

  if (groupBy.value === 'status') {
    return groupRowsByLabel(
      items.value,
      '_statusGroup',
      (item) => t(`resources.projects.status.${item.status}`),
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
  return groupBy.value === 'status' ? '_statusGroup' : '_customerGroup'
})

onMounted(() => {
  void usersStore.ensureLoaded()
  if (!customersStore.items.length) void customersStore.refresh()
  if (!productsStore.items.length) void productsStore.refresh()
})

// Server-side sort. The controlled sortField and sortOrder keep the header
// icon in step with the view's sort control.
function onSort(event: DataTableSortEvent): void {
  if (typeof event.sortField === 'string' && event.sortOrder) {
    store.setSort(event.sortField as ProjectSortBy, event.sortOrder === 1 ? 'asc' : 'desc')
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
    class="phone-columns projects-table clickable-rows"
    @row-contextmenu="onRowContextMenu"
    selection-mode="single"
    @row-click="onRowClick"
    @row-select="onRowClick"
  >
    <template v-if="groupBy" #groupheader="{ data }">
      <div class="group-header">
        <i v-if="groupBy === 'status'" class="mdi mdi-check-circle-outline" aria-hidden="true" />
        <i v-else class="mdi mdi-domain" aria-hidden="true" />
        <span class="group-header-label">{{
          groupBy === 'status' ? data._statusGroup : data._customerGroup
        }}</span>
      </div>
    </template>

    <template #empty>
      <EmptyState />
    </template>

    <Column
      v-if="store.showActions"
      :header="t('resources.projects.columns.actions')"
      style="width: 8rem"
    >
      <template #body="{ data }: { data: ProjectResponse }">
        <div class="row-actions">
          <span v-tooltip.top="editTooltip(data)">
            <Button
              icon="mdi mdi-pencil"
              size="small"
              severity="secondary"
              text
              :disabled="!canEdit(data)"
              :aria-label="t('resources.projects.editProject')"
              @click.stop="onEditProject(data)"
            />
          </span>
          <span v-tooltip.top="deleteTooltip(data)">
            <Button
              icon="mdi mdi-delete-outline"
              size="small"
              severity="danger"
              text
              :disabled="!canManage || deleteBlockedReason(data) !== null"
              :aria-label="t('common.delete')"
              @click.stop="onDeleteProject(data)"
            />
          </span>
        </div>
      </template>
    </Column>

    <Column
      class="phone-col"
      field="status"
      :header="t('resources.projects.columns.status')"
      :show-filter-menu="false"
      style="width: 9rem"
    >
      <template #body="{ data }: { data: ProjectResponse }">
        <Tag
          :value="t(`resources.projects.status.${data.status}`)"
          :severity="projectStatusSeverity[data.status]"
        />
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="statusOptions"
          option-label="label"
          option-value="value"
          show-clear
          :aria-label="t('common.filterBy', { column: t('resources.projects.columns.status') })"
          size="small"
          fluid
          @change="filterCallback()"
        />
      </template>
    </Column>

    <Column
      class="phone-col"
      field="project_number"
      :header="t('resources.projects.columns.projectNumber')"
      :show-filter-menu="false"
      sortable
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.projects.filters.projectNumber')"
          :aria-label="t('common.filterBy', { column: t('resources.projects.columns.projectNumber') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="product_id"
      :header="t('resources.projects.columns.product')"
      :show-filter-menu="false"
      style="width: 10rem"
    >
      <template #body="{ data }: { data: ProjectResponse }">
        <span v-if="data.product">{{ data.product.product_number }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="productFilterOptions"
          option-label="product_number"
          option-value="id"
          :placeholder="t('resources.projects.filters.any')"
          :aria-label="t('common.filterBy', { column: t('resources.projects.columns.product') })"
          show-clear
          filter
          size="small"
          fluid
          @change="filterCallback()"
        >
          <template #option="{ option }">
            <span>{{ option.product_number }}</span>
            <ArchivedOptionTag v-if="option.archived" />
          </template>
        </Select>
      </template>
    </Column>

    <Column
      class="phone-col"
      field="customer_id"
      :header="t('resources.projects.columns.customer')"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: ProjectResponse }">
        <span v-if="data.customer">{{ data.customer.name }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="customerFilterOptions"
          option-label="name"
          option-value="id"
          :placeholder="t('resources.projects.filters.customer')"
          :aria-label="t('common.filterBy', { column: t('resources.projects.columns.customer') })"
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
      :header="t('resources.projects.columns.description')"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: ProjectResponse }">
        <span v-if="data.description">{{ data.description }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.projects.filters.description')"
          :aria-label="t('common.filterBy', { column: t('resources.projects.columns.description') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="production_time_budget"
      :header="t('resources.projects.fields.productionTimeBudget')"
      style="width: 9rem"
    >
      <template #body="{ data }: { data: ProjectResponse }">
        <span v-if="data.production_time_budget !== null"
          >{{ data.production_time_budget }} min</span
        >
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>

    <Column
      field="required_delivery_date_made"
      :header="t('resources.projects.fields.requiredDeliveryDateMade')"
      :show-filter-menu="false"
      style="width: 10rem"
    >
      <template #body="{ data }: { data: ProjectResponse }">
        {{ formatDateOrDash(data.required_delivery_date_made) }}
      </template>
      <template #filter>
        <DemandDateRangeFilter
          v-model="deliveryMadeRange"
          :placeholder="t('resources.projects.filters.dateRange')"
          @clear-click="deliveryMadeRange = null"
        />
      </template>
    </Column>

    <Column
      field="required_delivery_date_bought"
      :header="t('resources.projects.fields.requiredDeliveryDateBought')"
      :show-filter-menu="false"
      style="width: 10rem"
    >
      <template #body="{ data }: { data: ProjectResponse }">
        {{ formatDateOrDash(data.required_delivery_date_bought) }}
      </template>
      <template #filter>
        <DemandDateRangeFilter
          v-model="deliveryBoughtRange"
          :placeholder="t('resources.projects.filters.dateRange')"
          @clear-click="deliveryBoughtRange = null"
        />
      </template>
    </Column>

    <Column
      field="designated_user_id"
      :header="t('resources.projects.columns.designatedUser')"
      :show-filter-menu="false"
      style="width: 10rem"
    >
      <template #body="{ data }: { data: ProjectResponse }">
        <UserAvatarPreview :user="usersStore.getById(data.designated_user_id) ?? null" />
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="usersStore.users"
          option-label="full_name"
          option-value="id"
          :loading="usersStore.loading"
          :placeholder="t('resources.projects.filters.any')"
          :aria-label="t('common.filterBy', { column: t('resources.projects.columns.designatedUser') })"
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
      :header="t('resources.projects.columns.created')"
      :show-filter-menu="false"
      sortable
      style="width: 10rem"
    >
      <template #body="{ data }: { data: ProjectResponse }">
        <UserDateCell :date="data.created" :user="data.creator" />
      </template>
      <template #filter>
        <UserDateFilter
          v-model:user-id="creatorId"
          v-model:range="createdRange"
          :column="t('resources.projects.columns.created')"
          :placeholder="t('resources.projects.filters.any')"
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

  <ProjectFormDialog
    v-model:visible="editDialogVisible"
    :project="editingProject"
    @saved="onSaved"
  />

  <ProjectItemsDialog v-model:visible="itemsDialogVisible" :project="itemsDialogProject" />
</template>

<style scoped lang="scss">
.projects-table {
  width: 100%;
}

.group-header-label {
  font-weight: bold;
  padding-left: var(--space-4);
}
</style>
