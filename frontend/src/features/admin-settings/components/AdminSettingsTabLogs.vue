<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { FilterMatchMode } from '@openvue/core/api'
import { formatISODateTime as formatDateTime, toDateKey } from '@/core/utils/dates'
import { filterMetaValue, hasActiveFilterMeta } from '@/core/utils/filterMeta'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import type { DataTableFilterMeta, DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { getLogs } from '../api/getLogs'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useClipboard } from '@/core/composables/useClipboard'
import { useServerTable } from '@/core/composables/useServerTable'
import type { LogFilterParams, LogResponse } from '../types/adminSettingsTypes'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useDateRangeTupleFilter } from '@/shared/composables/useDateRangeFilter'
import type { DateRangeTuple } from '@/shared/composables/useDateRangeFilter'

const { t } = useI18n()
const { copyToClipboard } = useClipboard()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

function createEmptyFilters(): DataTableFilterMeta {
  return {
    username: { value: null, matchMode: FilterMatchMode.CONTAINS },
    level: { value: null, matchMode: FilterMatchMode.CONTAINS },
    method: { value: null, matchMode: FilterMatchMode.CONTAINS },
    path: { value: null, matchMode: FilterMatchMode.CONTAINS },
    status_code: { value: null, matchMode: FilterMatchMode.EQUALS },
    message: { value: null, matchMode: FilterMatchMode.CONTAINS },
    request_id: { value: null, matchMode: FilterMatchMode.EQUALS },
  }
}

const loading = ref(false)
watchLoadingBar(loading)
const items = ref<LogResponse[]>([])
const total = ref(0)
const filters = ref<DataTableFilterMeta>(createEmptyFilters())
const dateRange = ref<DateRangeTuple>([null, null])

const hasActiveFilters = computed(
  () => hasActiveFilterMeta(filters.value) || dateRange.value[0] !== null,
)

function buildParams(base: { skip: number; limit: number }): LogFilterParams {
  // Every filter cell is a text input, so a set filter holds a string.
  const getValue = (field: string): string | null => {
    const value = filterMetaValue(filters.value, field)
    return typeof value === 'string' && value ? value : null
  }

  const params: LogFilterParams = { ...base }

  const username = getValue('username')
  if (username) params.username_contains = username
  const level = getValue('level')
  if (level) params.level = level
  const method = getValue('method')
  if (method) params.method = method
  const path = getValue('path')
  if (path) params.path_contains = path
  const statusCode = Number(getValue('status_code'))
  if (Number.isInteger(statusCode) && statusCode > 0) params.status_code = statusCode
  const message = getValue('message')
  if (message) params.message_contains = message
  const requestId = getValue('request_id')
  if (requestId) params.request_id = requestId

  const [from, to] = dateRange.value
  if (from) params.from_timestamp = toDateKey(from)
  if (to) params.to_timestamp = toDateKey(to)

  return params
}

const {
  first,
  rows,
  fetchItems: load,
  resetAndFetch,
  onPage,
  onFilter,
} = useServerTable({
  fetchParams: ({ first, rows }) => buildParams({ skip: first, limit: rows }),
  fetch: async (params) => {
    loading.value = true
    try {
      const response = await getLogs(params)
      items.value = response.items
      total.value = response.total
    } finally {
      loading.value = false
    }
  },
})

function clearAll() {
  filters.value = createEmptyFilters()
  dateRange.value = [null, null]
  resetAndFetch()
}

const { getDateRangeModel, setDateRangeModel } = useDateRangeTupleFilter(dateRange, onFilter)

function levelSeverity(level: string | null): string {
  switch (level?.toUpperCase()) {
    case 'DEBUG':
      return 'secondary'
    case 'INFO':
      return 'info'
    case 'WARNING':
    case 'WARN':
      return 'warn'
    case 'ERROR':
    case 'CRITICAL':
      return 'danger'
    default:
      return 'secondary'
  }
}

function statusSeverity(code: number | null): string {
  if (code == null) return 'secondary'
  if (code < 300) return 'success'
  if (code < 400) return 'info'
  if (code < 500) return 'warn'
  return 'danger'
}

const cm = ref()
const contextMenuItem = ref<LogResponse | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const entry = contextMenuItem.value
  if (!entry) return []

  return [
    {
      label: t('common.copyUuid'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(entry.public_id),
    },
  ]
})
</script>

<template>
  <AdminSettingsTabShell table>
    <template #controls>
      <Toolbar>
        <template #start>
          <Button
            :label="t('common.reload')"
            icon="mdi mdi-sync"
            severity="contrast"
            text
            :loading="loading"
            @click="load"
          />
          <Button
            :label="t('common.clear')"
            icon="mdi mdi-filter-off-outline"
            severity="contrast"
            text
            :disabled="!hasActiveFilters"
            @click="clearAll"
          />
        </template>
      </Toolbar>
    </template>

    <DataTable
      :value="items"
      data-key="id"
      v-model:context-menu-selection="contextMenuItem"
      lazy
      paginator
      :total-records="total"
      :first="first"
      :rows="rows"
      :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
      v-model:filters="filters"
      filter-display="row"
      scrollable
      scroll-height="flex"
      resizable-columns
      column-resize-mode="expand"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      @page="onPage"
      @filter="onFilter"
      @row-contextmenu="onRowContextMenu"
    >
      <Column
        header="#"
        header-style="width: 3rem"
        body-style="text-align: right; color: var(--p-text-muted-color); font-size: 0.75rem"
      >
        <template #body="{ index }">{{ first + index + 1 }}</template>
      </Column>

      <Column
        field="timestamp"
        :header="t('settings.logs.columns.timestamp')"
        :show-filter-menu="false"
        style="width: 13rem"
      >
        <template #body="{ data }">{{ formatDateTime(data.timestamp) }}</template>
        <template #filter>
          <DatePicker
            :model-value="getDateRangeModel()"
            selection-mode="range"
            show-button-bar
            show-clear
            :placeholder="t('settings.logs.filters.dateRange')"
            :aria-label="t('common.filterBy', { column: t('settings.logs.columns.timestamp') })"
            size="small"
            fluid
            @update:model-value="setDateRangeModel"
            @clear-click="setDateRangeModel(null)"
          />
        </template>
      </Column>

      <Column
        field="username"
        :header="t('settings.logs.columns.username')"
        :show-filter-menu="false"
        style="width: 10rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            @input="filterCallback()"
            :placeholder="t('settings.logs.filters.username')"
            :aria-label="t('common.filterBy', { column: t('settings.logs.columns.username') })"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column
        field="level"
        :header="t('settings.logs.columns.level')"
        :show-filter-menu="false"
        style="width: 8rem"
      >
        <template #body="{ data }">
          <Tag
            v-if="data.level"
            :value="data.level.toUpperCase()"
            :severity="levelSeverity(data.level)"
          />
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            @input="filterCallback()"
            :placeholder="t('settings.logs.filters.level')"
            :aria-label="t('common.filterBy', { column: t('settings.logs.columns.level') })"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column
        field="method"
        :header="t('settings.logs.columns.method')"
        :show-filter-menu="false"
        style="width: 7rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            @input="filterCallback()"
            :placeholder="t('settings.logs.filters.method')"
            :aria-label="t('common.filterBy', { column: t('settings.logs.columns.method') })"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column
        field="status_code"
        :header="t('settings.logs.columns.statusCode')"
        :show-filter-menu="false"
        style="width: 7rem"
      >
        <template #body="{ data }">
          <Tag
            v-if="data.status_code != null"
            :value="String(data.status_code)"
            :severity="statusSeverity(data.status_code)"
          />
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            type="number"
            @input="filterCallback()"
            :placeholder="t('settings.logs.filters.statusCode')"
            :aria-label="t('common.filterBy', { column: t('settings.logs.columns.statusCode') })"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column
        field="path"
        :header="t('settings.logs.columns.path')"
        :show-filter-menu="false"
        style="width: 16rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            @input="filterCallback()"
            :placeholder="t('settings.logs.filters.path')"
            :aria-label="t('common.filterBy', { column: t('settings.logs.columns.path') })"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column
        field="request_id"
        :header="t('settings.logs.columns.requestId')"
        :show-filter-menu="false"
        style="width: 9rem"
      >
        <template #body="{ data }">
          <span
            v-if="data.request_id"
            style="font-family: monospace; font-size: var(--font-size-xs); color: var(--p-text-muted-color)"
            >{{ data.request_id }}</span
          >
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            @input="filterCallback()"
            :placeholder="t('settings.logs.filters.requestId')"
            :aria-label="t('common.filterBy', { column: t('settings.logs.columns.requestId') })"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column field="message" :header="t('settings.logs.columns.message')" :show-filter-menu="false">
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            @input="filterCallback()"
            :placeholder="t('settings.logs.filters.message')"
            :aria-label="t('common.filterBy', { column: t('settings.logs.columns.message') })"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column />

      <template #empty>
        <EmptyState />
      </template>
    </DataTable>

    <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />
  </AdminSettingsTabShell>
</template>
