<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import type { DataTableSortEvent } from 'openvue/datatable'

import { Permission } from '@/core/auth/permissions'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useServerTable } from '@/core/composables/useServerTable'
import { usePermissions } from '@/core/composables/usePermissions'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { groupRowsByLabel } from '@/core/utils/tableRowGrouping'
import ContactLinks from '@/shared/components/ContactLinks.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useFilterMetaWatch } from '@/shared/composables/useFilterMetaWatch'
import { useManagementResourceActions } from '@/shared/composables/useManagementResourceActions'
import { getContact } from '../api/contactsApi'
import { useContactUsage } from '../composables/useContactUsage'
import { useContactsStore } from '../stores/contactsStore'
import { contactDisplayName } from '../utils/contactLabels'
import ContactFormDialog from './ContactFormDialog.vue'
import ContactOrganisationCell from './ContactOrganisationCell.vue'
import ContactUsedIn from './ContactUsedIn.vue'
import type { ContactSortBy } from '../types/contactRequest'
import type { ContactResponse } from '../types/contactResponse'

/**
 * The contacts table of the Resources page. A row opens the contact's
 * dialog, and `?contact=<id>` in the URL, which the global search links to,
 * opens it as well.
 */

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useContactsStore()
const { tableItems: items, loading, filters, clearTrigger, search, sortBy, sortDir, groupBy, showArchived } =
  storeToRefs(store)
watchLoadingBar(loading)
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const canWrite = computed(() => hasPermission(Permission.WRITE_CONTACTS))
const { usage } = useContactUsage(items)

const organisationKindOptions = computed(() =>
  (['customer', 'supplier', 'none'] as const).map((value) => ({
    value,
    label: t(`contacts.organisationKinds.${value}`),
  })),
)

const dialogVisible = ref(false)
const editing = ref<ContactResponse | null>(null)

function openContact(contact: ContactResponse): void {
  editing.value = contact
  dialogVisible.value = true
}

const {
  cm,
  contextMenuTarget,
  contextMenuItems,
  onRowContextMenu,
  onRowClick,
  onDelete: onArchive,
  onRestore,
} = useManagementResourceActions<ContactResponse>(store, {
  i18nPrefix: 'contacts',
  entityLabel: (contact) => contactDisplayName(t, contact),
  deletePermission: Permission.WRITE_CONTACTS,
  archivable: { isArchived: (contact) => contact.archived },
  showDetailItem: false,
  onShowDetail: openContact,
  editItem: (contact) => ({
    label: t('contacts.editContact'),
    icon: 'mdi mdi-pencil',
    command: () => openContact(contact),
  }),
})

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: ({ first, rows }) => ({ skip: first, limit: rows }),
  fetch: (params) => store.refreshTable(params),
})

useFilterMetaWatch(filters, ['name', 'email', 'phone'], resetAndFetchDebounced)
useFilterMetaWatch(filters, ['organisation_kind'], resetAndFetch)
watch(search, resetAndFetchDebounced)
watch([showArchived, clearTrigger, sortBy, sortDir], resetAndFetch)
watch(
  () => store.refreshTrigger,
  () => fetchItems(),
)
// Quietly, as every list follows other users' changes.
useLiveRefresh([LiveResource.CONTACTS, LiveResource.PRODUCT_CONTACTS, LiveResource.PROJECT_CONTACTS], () =>
  fetchItems(),
)

async function openFromRoute(): Promise<void> {
  const id = Number(route.query.contact)
  if (!Number.isInteger(id) || id <= 0) return
  try {
    openContact(await getContact(id))
  } catch {
    // A contact that is gone or not readable leaves the table as it is.
  }
  const query = { ...route.query }
  delete query.contact
  void router.replace({ query })
}

onMounted(() => void openFromRoute())

const shownItems = computed(() => {
  if (groupBy.value !== 'organisation') return items.value
  return groupRowsByLabel(
    items.value,
    '_organisationGroup',
    (contact) => contact.organisation?.name ?? t('contacts.noOrganisation'),
  )
})

function onSort(event: DataTableSortEvent): void {
  if (typeof event.sortField === 'string' && event.sortOrder) {
    store.setSort(event.sortField as ContactSortBy, event.sortOrder === 1 ? 'asc' : 'desc')
  } else {
    store.clearSort()
  }
}

function onSaved(): void {
  store.triggerRefresh()
}
</script>

<template>
  <DataTable
    :value="shownItems"
    v-model:filters="filters"
    v-model:context-menu-selection="contextMenuTarget"
    filter-display="row"
    data-key="id"
    lazy
    paginator
    always-show-paginator
    :total-records="store.total"
    :first="first"
    :rows="rows"
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    :sort-field="sortBy && sortBy !== 'organisation' ? sortBy : undefined"
    :sort-order="sortBy && sortBy !== 'organisation' ? (sortDir === 'asc' ? 1 : -1) : undefined"
    removable-sort
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    scrollable
    scroll-height="flex"
    :row-group-mode="groupBy ? 'subheader' : undefined"
    :group-rows-by="groupBy ? '_organisationGroup' : undefined"
    selection-mode="single"
    class="phone-columns contacts-table clickable-rows"
    data-testid="contacts-table"
    @page="onPage"
    @sort="onSort"
    @row-contextmenu="onRowContextMenu"
    @row-click="onRowClick"
    @row-select="onRowClick"
  >
    <template v-if="groupBy" #groupheader="{ data }">
      <div class="group-header">
        <i class="mdi mdi-domain" aria-hidden="true" />
        <span class="group-header-label">{{ data._organisationGroup }}</span>
      </div>
    </template>
    <template #empty>
      <EmptyState />
    </template>

    <Column header="#" body-class="row-number" class="column-fit phone-row-number">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>

    <Column v-if="store.showActions" :header="t('contacts.columns.actions')" class="column-fit">
      <template #body="{ data }: { data: ContactResponse }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            v-tooltip.top.focus="t('contacts.editContact')"
            :aria-label="t('contacts.editContact')"
            @click.stop="openContact(data)"
          />
          <Button
            v-if="!data.archived"
            icon="mdi mdi-archive-outline"
            size="small"
            severity="danger"
            text
            :disabled="!canWrite"
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
            :disabled="!canWrite || !!data.anonymised_at"
            v-tooltip.top.focus="t('common.restore')"
            :aria-label="t('common.restore')"
            @click.stop="onRestore(data)"
          />
        </div>
      </template>
    </Column>

    <Column
      field="name"
      :header="t('contacts.columns.name')"
      :show-filter-menu="false"
      sortable
      class="column-fit phone-col"
    >
      <template #body="{ data }: { data: ContactResponse }">
        <div class="name-cell">
          <span class="name-line">
            <span class="contact-name" :class="{ 'text-muted': data.anonymised_at }">
              {{ contactDisplayName(t, data) }}
            </span>
            <Tag
              v-if="data.archived"
              :value="t('common.archivedTag')"
              severity="warn"
              icon="mdi mdi-archive-outline"
            />
          </span>
          <small v-if="data.role" class="text-muted">{{ data.role }}</small>
        </div>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          :placeholder="t('contacts.filters.name')"
          :aria-label="t('common.filterBy', { column: t('contacts.columns.name') })"
          size="small"
          class="filter-wide"
          fluid
          @input="filterCallback()"
        />
      </template>
    </Column>

    <Column
      field="email"
      :header="t('contacts.columns.email')"
      :show-filter-menu="false"
      class="column-fit phone-col"
    >
      <template #body="{ data }: { data: ContactResponse }">
        <ContactLinks :email="data.email" :phone="data.phone ?? data.mobile" />
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          :placeholder="t('contacts.filters.email')"
          :aria-label="t('common.filterBy', { column: t('contacts.columns.email') })"
          size="small"
          class="filter-wide"
          fluid
          @input="filterCallback()"
        />
      </template>
    </Column>

    <Column field="phone" :header="t('contacts.columns.phone')" :show-filter-menu="false" class="column-fit">
      <template #body="{ data }: { data: ContactResponse }">
        <div v-if="data.phone || data.mobile" class="phone-cell">
          <span v-if="data.phone">{{ data.phone }}</span>
          <span v-if="data.mobile" class="text-muted">{{ data.mobile }}</span>
        </div>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          :placeholder="t('contacts.filters.phone')"
          :aria-label="t('common.filterBy', { column: t('contacts.columns.phone') })"
          size="small"
          class="filter-narrow"
          fluid
          @input="filterCallback()"
        />
      </template>
    </Column>

    <Column
      field="organisation_kind"
      :header="t('contacts.columns.organisation')"
      :show-filter-menu="false"
      class="column-fit"
    >
      <template #body="{ data }: { data: ContactResponse }">
        <ContactOrganisationCell :organisation="data.organisation" />
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="organisationKindOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('contacts.filters.any')"
          :aria-label="t('common.filterBy', { column: t('contacts.columns.organisation') })"
          show-clear
          size="small"
          class="filter-wide"
          fluid
          @change="filterCallback()"
        />
      </template>
    </Column>

    <Column :header="t('contacts.columns.usedIn')" class="column-fit">
      <template #body="{ data }: { data: ContactResponse }">
        <ContactUsedIn :contact="data" :usage="usage.get(data.id)" />
      </template>
    </Column>

    <Column />
  </DataTable>

  <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuTarget = null" />

  <ContactFormDialog v-model:visible="dialogVisible" :contact="editing" @saved="onSaved" />
</template>

<style scoped lang="scss">
.contacts-table {
  width: 100%;
}

// The columns fit their content, so the filter inputs above them set a
// floor that keeps a typed search readable.
.filter-wide {
  min-width: 11rem;
}

.filter-narrow {
  min-width: 8rem;
}

.name-cell,
.phone-cell {
  display: flex;
  flex-direction: column;
}

.name-line {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.contact-name {
  font-weight: 600;
}

.group-header-label {
  font-weight: bold;
  padding-left: var(--space-4);
}
</style>
