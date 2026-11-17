<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { storeToRefs } from 'pinia'

import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { usePrintersStore } from '../stores/printersStore'
import { testPrintPrinter } from '../api/testPrintPrinter'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useServerTable } from '@/core/composables/useServerTable'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { extractApiError } from '@/core/utils/errors'
import { useFilterMetaWatch } from '@/shared/composables/useFilterMetaWatch'
import { useFilterMetaModel } from '@/shared/composables/useFilterMetaModel'
import { useManagementResourceActions } from '@/shared/composables/useManagementResourceActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import EmptyState from '@/shared/components/EmptyState.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'

import type { PrinterResponse } from '../types/printerResponse'
import type { PrinterKind } from '../types/printerRequest'
import { groupRowsByLabel } from '@/core/utils/tableRowGrouping'

const emit = defineEmits<{
  edit: [printer: PrinterResponse]
  status: [printer: PrinterResponse]
  history: [printer: PrinterResponse]
}>()

const { t } = useI18n()
const toast = useAppToast()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const store = usePrintersStore()
const { filters, search, sortBy, sortDir, groupBy, showActions, showArchived } = storeToRefs(store)
const creatorId = useFilterMetaModel<number>(filters, 'creator_id')
const changedById = useFilterMetaModel<number>(filters, 'changed_by_id')
watchLoadingBar(() => store.loading)

const kindOptions = computed<{ label: string; value: PrinterKind }[]>(() =>
  (['zpl_label', 'ipp_document'] as const).map((kind) => ({
    label: t(`printers.kinds.${kind}`),
    value: kind,
  })),
)

const enabledOptions = computed<{ label: string; value: boolean }[]>(() => [
  { label: t('common.yes'), value: true },
  { label: t('common.no'), value: false },
])

const canWrite = computed(() => hasPermission(Permission.WRITE_PRINTERS))
const canDelete = computed(() => hasPermission(Permission.WRITE_PRINTERS))
const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))
// The status query talks to the printer, so the backend treats it like a
// print and asks for Print Documents; the print history is the print audit
// trail and needs Read Settings.
const canReadHistory = computed(() => hasPermission(Permission.READ_SETTINGS))

// The tooltips of the disabled row buttons and the titles of the disabled
// menu entries, naming the missing permission.
const writeBlocked = computed(() => missing(Permission.WRITE_PRINTERS))
const deleteBlocked = computed(() => missing(Permission.WRITE_PRINTERS))
const printBlocked = computed(() => missing(Permission.PRINT_DOCUMENTS))
const historyBlocked = computed(() => missing(Permission.READ_SETTINGS))

const testPrinting = ref<number | null>(null)

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: ({ first, rows }) => ({ skip: first, limit: rows }),
  fetch: (params) => store.refreshTable(params),
})

watch(search, resetAndFetchDebounced)

// The typed name filter is debounced, dropdown filters fetch right away.
useFilterMetaWatch(filters, ['name'], resetAndFetchDebounced)
useFilterMetaWatch(filters, ['kind', 'enabled', 'creator_id', 'changed_by_id'], resetAndFetch)

watch(showArchived, resetAndFetch)

watch([sortBy, sortDir], () => fetchItems())

watch(
  () => store.refreshTrigger,
  () => fetchItems(),
)

const groupedItems = computed(() => {
  if (groupBy.value === 'kind') {
    return groupRowsByLabel(store.tableItems, '_printerGroup', (item) => t(`printers.kinds.${item.kind}`))
  }
  if (groupBy.value === 'location') {
    return groupRowsByLabel(store.tableItems, '_printerGroup', (item) => item.location ?? getEmptyPlaceholder())
  }
  return store.tableItems
})

defineExpose({ refresh: fetchItems })

function onEdit(printer: PrinterResponse): void {
  emit('edit', printer)
}

function onStatus(printer: PrinterResponse): void {
  emit('status', printer)
}

function onHistory(printer: PrinterResponse): void {
  emit('history', printer)
}

async function onTestPrint(printer: PrinterResponse): Promise<void> {
  testPrinting.value = printer.id
  try {
    await testPrintPrinter(printer.id)
    toast.success(printer.name, t('printers.testPrintSent'))
  } catch (e) {
    toast.error(printer.name, extractApiError(e) ?? t('printers.errors.unknown'))
  } finally {
    testPrinting.value = null
  }
}

// Context menu and the archive confirm come from useManagementResourceActions.
// The status dialog stands in for a detail dialog, so the menu lists it with
// the other printer entries instead of the built-in "Show details".
const {
  cm,
  contextMenuTarget: contextMenuItem,
  contextMenuItems,
  onRowContextMenu,
  onDelete: onArchive,
  onRestore,
} = useManagementResourceActions<PrinterResponse>(store, {
  i18nPrefix: 'printers',
  entityLabel: (printer) => printer.name,
  deletePermission: Permission.WRITE_PRINTERS,
  archivable: { isArchived: (printer) => printer.archived },
  showDetailItem: false,
  extraItems: (printer) => [
    {
      label: t('printers.editPrinter'),
      icon: 'mdi mdi-pencil',
      disabled: !canWrite.value,
      title: writeBlocked.value || undefined,
      command: () => onEdit(printer),
    },
    {
      label: t('printers.status.title'),
      icon: 'mdi mdi-information-outline',
      disabled: !canPrint.value,
      title: printBlocked.value || undefined,
      command: () => onStatus(printer),
    },
    {
      label: t('printers.testPrint'),
      icon: 'mdi mdi-printer-check',
      disabled: !canPrint.value,
      title: printBlocked.value || undefined,
      command: () => void onTestPrint(printer),
    },
    {
      label: t('printers.history.menuLabel'),
      icon: 'mdi mdi-history',
      disabled: !canReadHistory.value,
      title: historyBlocked.value || undefined,
      command: () => onHistory(printer),
    },
  ],
})
</script>

<template>
  <DataTable
    :value="groupedItems"
    v-model:filters="filters"
    filter-display="row"
    data-key="id"
    lazy
    paginator
    :total-records="store.total"
    :first="first"
    :rows="rows"
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    @page="onPage"
    scrollable
    scroll-height="flex"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    :row-group-mode="groupBy ? 'subheader' : undefined"
    group-rows-by="_printerGroup"
    resizable-columns
    column-resize-mode="fit"
    v-model:context-menu-selection="contextMenuItem"
    @row-contextmenu="onRowContextMenu"
  >
    <template v-if="groupBy" #groupheader="{ data }">
      <div class="group-header">
        <i
          :class="`mdi ${groupBy === 'kind' ? 'mdi-printer-outline' : 'mdi-map-marker-outline'}`"
          aria-hidden="true"
        />
        <span class="group-header-label">{{ data._printerGroup }}</span>
      </div>
    </template>

    <Column header="#" header-style="width: 3rem" body-class="row-number">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>
    <Column v-if="showActions" :header="t('printers.columns.actions')" style="width: 11rem">
      <template #body="{ data }">
        <div class="row-actions">
          <!-- Each span carries the missing-permission tooltip, since a
               disabled button shows none of its own. -->
          <span v-tooltip.top="printBlocked || undefined">
            <Button
              icon="mdi mdi-information-outline"
              size="small"
              severity="secondary"
              text
              :disabled="!canPrint"
              v-tooltip.top.focus="t('printers.status.title')"
              :aria-label="t('printers.status.title')"
              data-testid="printer-status"
              @click="onStatus(data as PrinterResponse)"
            />
          </span>
          <span v-tooltip.top="printBlocked || undefined">
            <Button
              icon="mdi mdi-printer-check"
              size="small"
              severity="secondary"
              text
              :disabled="!canPrint || testPrinting === (data as PrinterResponse).id"
              :loading="testPrinting === (data as PrinterResponse).id"
              v-tooltip.top.focus="t('printers.testPrint')"
              :aria-label="t('printers.testPrint')"
              data-testid="printer-test-print"
              @click="onTestPrint(data as PrinterResponse)"
            />
          </span>
          <span v-tooltip.top="writeBlocked || undefined">
            <Button
              icon="mdi mdi-pencil"
              size="small"
              severity="secondary"
              text
              :disabled="!canWrite"
              v-tooltip.top.focus="t('printers.editPrinter')"
              :aria-label="t('printers.editPrinter')"
              data-testid="printer-edit"
              @click="onEdit(data as PrinterResponse)"
            />
          </span>
          <span v-if="(data as PrinterResponse).archived" v-tooltip.top="deleteBlocked || undefined">
            <Button
              icon="mdi mdi-archive-arrow-up-outline"
              size="small"
              severity="secondary"
              text
              :disabled="!canDelete"
              v-tooltip.top.focus="t('common.restore')"
              :aria-label="t('common.restore')"
              @click="onRestore(data as PrinterResponse)"
            />
          </span>
          <span v-else v-tooltip.top="deleteBlocked || undefined">
            <Button
              icon="mdi mdi-archive-outline"
              size="small"
              severity="danger"
              text
              :disabled="!canDelete"
              v-tooltip.top.focus="t('common.archive')"
              :aria-label="t('common.archive')"
              @click="onArchive(data as PrinterResponse)"
            />
          </span>
        </div>
      </template>
    </Column>


    <Column
      field="name"
      :header="t('printers.columns.name')"
      :show-filter-menu="false"
      style="min-width: 10rem"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('printers.filters.filterBy')"
          :aria-label="t('common.filterBy', { column: t('printers.columns.name') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column :header="t('printers.columns.location')" style="min-width: 10rem">
      <template #body="{ data }">
        <span v-if="(data as PrinterResponse).location">{{
          (data as PrinterResponse).location
        }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column
      filter-field="enabled"
      :header="t('printers.columns.enabled')"
      :show-filter-menu="false"
      style="width: 7rem"
    >
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="enabledOptions"
          option-label="label"
          option-value="value"
          show-clear
          :placeholder="t('printers.filters.any')"
          :aria-label="t('common.filterBy', { column: t('printers.columns.enabled') })"
          size="small"
          fluid
          @change="filterCallback()"
        />
      </template>
      <template #body="{ data }">
        <i
          :class="
            (data as PrinterResponse).enabled
              ? 'mdi mdi-check-circle-outline text-success'
              : 'mdi mdi-close-circle-outline text-muted'
          "
          aria-hidden="true"
        />
      </template>
    </Column>
    <Column
      filter-field="kind"
      :header="t('printers.columns.kind')"
      :show-filter-menu="false"
      style="width: 9rem"
    >
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="kindOptions"
          option-label="label"
          option-value="value"
          show-clear
          :placeholder="t('printers.filters.any')"
          :aria-label="t('common.filterBy', { column: t('printers.columns.kind') })"
          size="small"
          fluid
          @change="filterCallback()"
        />
      </template>
      <template #body="{ data }">
        <Tag :value="t(`printers.kinds.${(data as PrinterResponse).kind}`)" />
      </template>
    </Column>
    <Column v-if="showArchived" :header="t('common.archivedTag')" style="width: 7rem">
      <template #body="{ data }">
        <Tag
          v-if="(data as PrinterResponse).archived"
          :value="t('common.archivedTag')"
          severity="warn"
          icon="mdi mdi-archive-outline"
          v-tooltip.top="t('common.archivedTagTooltip')"
        />
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('printers.columns.connection')" style="min-width: 12rem">
      <template #body="{ data }"
        >{{ (data as PrinterResponse).host }}:{{ (data as PrinterResponse).port }}</template
      >
    </Column>
    <Column
      filter-field="creator_id"
      :header="t('printers.columns.created')"
      :show-filter-menu="false"
      style="width: 10rem"
    >
      <template #body="{ data }">
        <UserDateCell
          :date="(data as PrinterResponse).created"
          :user-id="(data as PrinterResponse).creator_id"
          :name="(data as PrinterResponse).creator_full_name"
        />
      </template>
      <template #filter>
        <UserDateFilter
          v-model:user-id="creatorId"
          :column="t('printers.columns.created')"
          :placeholder="t('printers.filters.any')"
          user-only
        />
      </template>
    </Column>
    <Column
      filter-field="changed_by_id"
      :header="t('printers.columns.changed')"
      :show-filter-menu="false"
      style="width: 10rem"
    >
      <template #body="{ data }">
        <UserDateCell
          :date="(data as PrinterResponse).changed"
          :user-id="(data as PrinterResponse).changed_by_id"
          :name="(data as PrinterResponse).changed_by_full_name"
        />
      </template>
      <template #filter>
        <UserDateFilter
          v-model:user-id="changedById"
          :column="t('printers.columns.changed')"
          :placeholder="t('printers.filters.any')"
          user-only
        />
      </template>
    </Column>
    <Column style="width: 100%" />

    <template #empty>
      <EmptyState :message="t('printers.table.empty')" />
    </template>
  </DataTable>

  <ContextMenu ref="cm" :model="contextMenuItems" :pt="disabledItemTooltipPt" @hide="contextMenuItem = null" />
</template>

<style scoped lang="scss">
.group-header-label {
  font-weight: bold;
  padding-left: var(--space-4);
}

.text-success {
  color: var(--p-green-500);
}
</style>
