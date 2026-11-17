<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { DataTableFilterMeta, DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { getSettingsAudit } from '../api/getSettingsAudit'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useClipboard } from '@/core/composables/useClipboard'
import { useServerTable } from '@/core/composables/useServerTable'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { buildSettingsAuditParams } from '../utils/settingsAuditParams'
import type { AdminSettingsAuditEntry } from '../types/adminSettingsTypes'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'

const { t } = useI18n()
const { copyToClipboard } = useClipboard()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

// Every settings_domain value the backend writes into the audit log.
const DOMAIN_OPTIONS = [
  'auth',
  'banner',
  'branding',
  'features',
  'general',
  'host',
  'made_items',
  'mail',
  'maintenance',
  'notifications',
  'orders',
  'pdm',
  'production',
  'retention',
  'security',
  'storage',
]

// OpenVue's row filter cells read their model from this object even when
// the column templates bind their own refs, so it must exist, but stays
// empty because nothing is filtered in the browser.
const NO_FILTER_META: DataTableFilterMeta = {}

const loading = ref(false)
watchLoadingBar(loading)
const items = ref<AdminSettingsAuditEntry[]>([])
const total = ref(0)

// The table filters on the server, so these refs feed the request rather
// than a OpenVue filters meta. Text waits for typing to settle, the person,
// the domain select and the date range refetch at once.
const changedById = ref<number | null>(null)
const settingsDomain = ref<string | null>(null)
const summary = ref<string | null>(null)
const changedFrom = ref<Date | null>(null)
const changedTo = ref<Date | null>(null)
const changedRange = useDateRangeFilter(changedFrom, changedTo)

const hasActiveFilters = computed(
  () =>
    changedById.value !== null ||
    !!settingsDomain.value ||
    !!summary.value ||
    changedFrom.value !== null ||
    changedTo.value !== null,
)

const {
  first,
  rows,
  fetchItems: load,
  resetAndFetch,
  resetAndFetchDebounced,
  onPage,
} = useServerTable({
  fetchParams: ({ first, rows }) =>
    buildSettingsAuditParams(
      { skip: first, limit: rows },
      {
        changedById: changedById.value,
        settingsDomain: settingsDomain.value,
        summary: summary.value,
        changedFrom: changedFrom.value,
        changedTo: changedTo.value,
      },
    ),
  fetch: async (params) => {
    loading.value = true
    try {
      const response = await getSettingsAudit(params)
      items.value = response.items
      total.value = response.total
    } finally {
      loading.value = false
    }
  },
})

watch(summary, resetAndFetchDebounced)
watch([changedById, settingsDomain, changedFrom, changedTo], resetAndFetch)

function clearAll() {
  changedById.value = null
  settingsDomain.value = null
  summary.value = null
  changedFrom.value = null
  changedTo.value = null
}

const cm = ref()
const contextMenuItem = ref<AdminSettingsAuditEntry | null>(null)

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
            icon="mdi mdi-refresh"
            severity="contrast"
            text
            :loading="loading"
            @click="load"
            :label="t('common.reload')"
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
      v-model:context-menu-selection="contextMenuItem"
      data-key="id"
      lazy
      paginator
      :total-records="total"
      :first="first"
      :rows="rows"
      :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
      :filters="NO_FILTER_META"
      filter-display="row"
      scrollable
      scroll-height="flex"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      @page="onPage"
      @row-contextmenu="onRowContextMenu"
    >
      <Column
        field="changed_at"
        :header="t('adminSettings.audit.columns.changedAt')"
        :show-filter-menu="false"
        style="width: 13rem"
      >
        <template #body="{ data }: { data: AdminSettingsAuditEntry }">
          <UserDateCell
            :date="data.changed_at"
            :user-id="data.changed_by_id"
            :name="data.changed_by_username"
            with-time
          />
        </template>
        <template #filter>
          <UserDateFilter
            v-model:user-id="changedById"
            v-model:range="changedRange"
            :column="t('adminSettings.audit.columns.changedAt')"
          />
        </template>
      </Column>
      <Column
        field="settings_domain"
        :header="t('adminSettings.audit.columns.domain')"
        :show-filter-menu="false"
        style="width: 11rem"
      >
        <template #filter>
          <Select
            v-model="settingsDomain"
            :options="DOMAIN_OPTIONS"
            :placeholder="t('adminSettings.audit.filterDomain')"
            :aria-label="t('common.filterBy', { column: t('adminSettings.audit.columns.domain') })"
            show-clear
            size="small"
            fluid
          />
        </template>
      </Column>
      <Column
        field="summary"
        :header="t('adminSettings.audit.columns.summary')"
        :show-filter-menu="false"
      >
        <template #filter>
          <InputText
            v-model="summary"
            :aria-label="t('common.filterBy', { column: t('adminSettings.audit.columns.summary') })"
            size="small"
            fluid
          />
        </template>
      </Column>

      <template #empty>
        <EmptyState />
      </template>
    </DataTable>

    <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />
  </AdminSettingsTabShell>
</template>
