<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { DataTableFilterMeta, DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { getSecurityEvents } from '../api/getSecurityEvents'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useClipboard } from '@/core/composables/useClipboard'
import { useServerTable } from '@/core/composables/useServerTable'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { buildSecurityEventParams } from '../utils/securityEventParams'
import type {
  SecurityEvent,
  SecurityEventOutcome,
  SecurityEventType,
} from '../types/adminSettingsTypes'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'

const { t, te } = useI18n()
const { copyToClipboard } = useClipboard()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

// Every event type the backend records, in the order the filter lists them.
const EVENT_TYPES: SecurityEventType[] = [
  'login',
  'login_throttled',
  'logout',
  'password_confirmation',
  'session_revoked',
  'user_created',
  'user_deactivated',
  'user_reactivated',
  'user_permissions_changed',
  'user_groups_changed',
  'group_created',
  'group_changed',
  'group_deleted',
  'pat_created',
  'pat_revoked',
  'api_key_created',
  'api_key_revoked',
  'terminal_key_created',
  'terminal_key_revoked',
  'password_changed',
  'totp_enabled',
  'totp_disabled',
  'totp_reset',
  'passkey_added',
  'passkey_removed',
]
const OUTCOMES: SecurityEventOutcome[] = ['success', 'failure']

// The detail values that name a fixed choice and are shown translated.
const TRANSLATED_DETAIL_KEYS = new Set(['method', 'reason', 'scope'])

const eventTypeOptions = computed(() =>
  EVENT_TYPES.map((value) => ({ value, label: t(`adminSettings.securityLog.types.${value}`) })),
)
const outcomeOptions = computed(() =>
  OUTCOMES.map((value) => ({ value, label: t(`adminSettings.securityLog.outcomes.${value}`) })),
)

// OpenVue's row filter cells read their model from this object even when
// the column templates bind their own refs, so it must exist, but stays
// empty because nothing is filtered in the browser.
const NO_FILTER_META: DataTableFilterMeta = {}

const loading = ref(false)
watchLoadingBar(loading)
const items = ref<SecurityEvent[]>([])
const total = ref(0)

// The table filters on the server, so these refs feed the request rather
// than a OpenVue filters meta. Every filter refetches at once.
const userId = ref<number | null>(null)
const eventType = ref<SecurityEventType | null>(null)
const outcome = ref<SecurityEventOutcome | null>(null)
const occurredFrom = ref<Date | null>(null)
const occurredTo = ref<Date | null>(null)
const occurredRange = useDateRangeFilter(occurredFrom, occurredTo)

const hasActiveFilters = computed(
  () =>
    userId.value !== null ||
    !!eventType.value ||
    !!outcome.value ||
    occurredFrom.value !== null ||
    occurredTo.value !== null,
)

const {
  first,
  rows,
  fetchItems: load,
  resetAndFetch,
  onPage,
} = useServerTable({
  fetchParams: ({ first, rows }) =>
    buildSecurityEventParams(
      { skip: first, limit: rows },
      {
        userId: userId.value,
        eventType: eventType.value,
        outcome: outcome.value,
        occurredFrom: occurredFrom.value,
        occurredTo: occurredTo.value,
      },
    ),
  fetch: async (params) => {
    loading.value = true
    try {
      const response = await getSecurityEvents(params)
      items.value = response.items
      total.value = response.total
    } finally {
      loading.value = false
    }
  },
})

watch([userId, eventType, outcome, occurredFrom, occurredTo], resetAndFetch)

function clearAll() {
  userId.value = null
  eventType.value = null
  outcome.value = null
  occurredFrom.value = null
  occurredTo.value = null
}

function targetText(event: SecurityEvent): string {
  if (event.target_username) return event.target_username
  if (event.target_user_id != null) return `#${event.target_user_id}`
  return ''
}

function detailValue(key: string, value: unknown): string {
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'boolean') return value ? t('common.yes') : t('common.no')
  const text = String(value)
  const valueKey = `adminSettings.securityLog.values.${text}`
  return TRANSLATED_DETAIL_KEYS.has(key) && te(valueKey) ? t(valueKey) : text
}

/** The event's details as one line, each known key with its label. */
function detailText(event: SecurityEvent): string {
  return Object.entries(event.detail)
    .filter(([, value]) => value != null && !(Array.isArray(value) && value.length === 0))
    .map(([key, value]) => {
      const labelKey = `adminSettings.securityLog.detail.${key}`
      return `${te(labelKey) ? t(labelKey) : key}: ${detailValue(key, value)}`
    })
    .join(' · ')
}

const cm = ref()
const contextMenuItem = ref<SecurityEvent | null>(null)

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
        field="occurred_at"
        :header="t('adminSettings.securityLog.columns.occurredAt')"
        :show-filter-menu="false"
        style="width: 13rem"
      >
        <template #body="{ data }: { data: SecurityEvent }">
          <UserDateCell
            :date="data.occurred_at"
            :user-id="data.actor_user_id"
            :name="data.actor_username"
            with-time
          />
        </template>
        <template #filter>
          <UserDateFilter
            v-model:user-id="userId"
            v-model:range="occurredRange"
            :column="t('adminSettings.securityLog.columns.occurredAt')"
          />
        </template>
      </Column>
      <Column
        field="event_type"
        :header="t('adminSettings.securityLog.columns.eventType')"
        :show-filter-menu="false"
        style="width: 15rem"
      >
        <template #body="{ data }: { data: SecurityEvent }">
          {{ t(`adminSettings.securityLog.types.${data.event_type}`) }}
        </template>
        <template #filter>
          <Select
            v-model="eventType"
            :options="eventTypeOptions"
            option-label="label"
            option-value="value"
            :placeholder="t('adminSettings.securityLog.filterEventType')"
            :aria-label="
              t('common.filterBy', { column: t('adminSettings.securityLog.columns.eventType') })
            "
            show-clear
            size="small"
            fluid
          />
        </template>
      </Column>
      <Column
        field="outcome"
        :header="t('adminSettings.securityLog.columns.outcome')"
        :show-filter-menu="false"
        style="width: 9rem"
      >
        <template #body="{ data }: { data: SecurityEvent }">
          <Tag
            :value="t(`adminSettings.securityLog.outcomes.${data.outcome}`)"
            :severity="data.outcome === 'failure' ? 'danger' : 'success'"
          />
        </template>
        <template #filter>
          <Select
            v-model="outcome"
            :options="outcomeOptions"
            option-label="label"
            option-value="value"
            :placeholder="t('adminSettings.securityLog.filterOutcome')"
            :aria-label="
              t('common.filterBy', { column: t('adminSettings.securityLog.columns.outcome') })
            "
            show-clear
            size="small"
            fluid
          />
        </template>
      </Column>
      <Column :header="t('adminSettings.securityLog.columns.target')" style="width: 11rem">
        <template #body="{ data }: { data: SecurityEvent }">{{ targetText(data) }}</template>
      </Column>
      <Column :header="t('adminSettings.securityLog.columns.detail')">
        <template #body="{ data }: { data: SecurityEvent }">{{ detailText(data) }}</template>
      </Column>
      <Column
        field="client_ip"
        :header="t('adminSettings.securityLog.columns.clientIp')"
        style="width: 10rem"
      >
        <template #body="{ data }: { data: SecurityEvent }">
          <span :title="data.user_agent ?? undefined">{{ data.client_ip }}</span>
        </template>
      </Column>

      <template #empty>
        <EmptyState />
      </template>
    </DataTable>

    <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />
  </AdminSettingsTabShell>
</template>
