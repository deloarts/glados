<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'
import { useAppToast } from '@/core/composables/useAppToast'

import type {
  DataTableFilterMeta,
  DataTableRowContextMenuEvent,
  DataTableSortEvent,
} from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { formatISODate, formatISODateTime } from '@/core/utils/dates'
import { permissionLabel, permissionSeverity } from '@/shared/utils/permissionLabels'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useClipboard } from '@/core/composables/useClipboard'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useServerTable } from '@/core/composables/useServerTable'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import TokenUsageLogDialog from './TokenUsageLogDialog.vue'
import DemandDateRangeFilter from '@/shared/components/demands/DemandDateRangeFilter.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import type { TokenApi } from '@/shared/api/createTokenApi'
import type { TokenStoreInstance } from '@/shared/stores/createTokenStore'
import type { TokenSortBy, TokenSummary } from '@/shared/types/tokenTypes'
import EmptyState from '@/shared/components/EmptyState.vue'

const { t } = useI18n()
const confirm = useConfirm()
const appToast = useAppToast()
const { copyToClipboard } = useClipboard()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const props = defineProps<{
  store: TokenStoreInstance
  api: TokenApi
  canManage: boolean
  i18nPrefix: string
  /**
   * API keys only, resolves created_by_id to a display name, which the
   * created column shows below the date.
   */
  resolveCreatorName?: (id: number) => string
  /**
   * The tooltip of the disabled revoke button that names the missing
   * permission, '' or unset while revoking is allowed.
   */
  manageBlocked?: string
}>()

const usageLogVisible = ref(false)
const usageLogToken = ref<TokenSummary | null>(null)

watchLoadingBar(() => props.store.loading)
const { sortBy, sortDir, nameFilter, prefixFilter, createdFrom, createdTo, expiryFilter } =
  storeToRefs(props.store)

// The list filters on the server through the store's filter state, which
// the row filter cells bind directly. OpenVue still reads each cell's model
// from a filters object, so the table gets this empty one.
const NO_FILTER_META: DataTableFilterMeta = {}

const createdRange = useDateRangeFilter(createdFrom, createdTo)

const expiryOptions = computed(() => [
  { value: 'never', label: tt('neverExpires') },
  { value: 'expired', label: tt('expired') },
  { value: 'active', label: tt('filters.notExpired') },
])

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: ({ first, rows }) => ({ skip: first, limit: rows }),
  fetch: (params) => props.store.refresh(params),
})

watch(
  () => props.store.refreshTrigger,
  () => fetchItems(),
)

watch([sortBy, sortDir], () => {
  resetAndFetch()
})

watch([nameFilter, prefixFilter], resetAndFetchDebounced)
watch([createdFrom, createdTo, expiryFilter], resetAndFetch)

// Server-side sort: under `lazy` OpenVue only toggles its own header icon
// and emits @sort; nothing fetched before this was wired. Controlled
// sortField/sortOrder (below, on the DataTable) keeps the header icon
// honest if sort is ever changed from elsewhere.
function onSort(event: DataTableSortEvent): void {
  if (typeof event.sortField === 'string' && event.sortOrder) {
    props.store.setSort(event.sortField as TokenSortBy, event.sortOrder === 1 ? 'asc' : 'desc')
  } else {
    props.store.clearSort()
  }
}

function tt(key: string, params?: Record<string, unknown>): string {
  return t(`${props.i18nPrefix}.${key}`, params ?? {})
}

function onShowUsageLog(token: TokenSummary): void {
  usageLogToken.value = token
  usageLogVisible.value = true
}

function onRevoke(token: TokenSummary): void {
  async function onAccept(): Promise<void> {
    try {
      await props.store.revoke(token.id)
      appToast.success(token.name, tt('revoked'))
    } catch {
      appToast.error(tt('errors.unknown'))
    }
  }

  confirm.require({
    message: tt('revokeConfirm', { name: token.name }),
    header: tt('revokeButton'),
    icon: 'mdi mdi-cancel',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: tt('revokeButton'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

const cm = ref()
const contextMenuItem = ref<TokenSummary | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const token = contextMenuItem.value
  if (!token) return []

  return [
    {
      label: t('common.copyUuid'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(token.public_id),
    },
  ]
})
</script>

<template>
  <DataTable
    :value="store.tokens"
    v-model:context-menu-selection="contextMenuItem"
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
    :filters="NO_FILTER_META"
    filter-display="row"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    @row-contextmenu="onRowContextMenu"
  >
    <template #empty>
      <EmptyState :message="tt('empty')" />
    </template>

    <Column :header="tt('columns.actions')" style="width: 6rem">
      <template #body="{ data }: { data: TokenSummary }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-format-list-bulleted"
            size="small"
            severity="secondary"
            text
            v-tooltip.top.focus="tt('usageLogButton')"
            :aria-label="tt('usageLogButton')"
            @click="onShowUsageLog(data)"
          />
          <span v-if="manageBlocked" v-tooltip.top="manageBlocked">
            <Button
              icon="mdi mdi-cancel"
              size="small"
              severity="danger"
              text
              disabled
              :aria-label="tt('revokeButton')"
              data-testid="token-revoke"
            />
          </span>
          <Button
            v-else
            icon="mdi mdi-cancel"
            size="small"
            severity="danger"
            text
            :disabled="!canManage"
            v-tooltip.top.focus="tt('revokeButton')"
            :aria-label="tt('revokeButton')"
            data-testid="token-revoke"
            @click="onRevoke(data)"
          />
        </div>
      </template>
    </Column>

    <Column
      field="name"
      :header="tt('columns.name')"
      :show-filter-menu="false"
      style="min-width: 12rem"
      sortable
    >
      <template #body="{ data }: { data: TokenSummary }">
        <span class="name-cell">
          {{ data.name }}
          <Tag
            v-if="data.kind === 'terminal'"
            :value="tt('kindTerminal')"
            severity="info"
            icon="mdi mdi-monitor-dashboard"
            v-tooltip.top="tt('kindTerminalTooltip')"
            data-testid="token-kind-terminal"
          />
        </span>
      </template>
      <template #filter>
        <InputText
          v-model="nameFilter"
          :aria-label="t('common.filterBy', { column: tt('columns.name') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="token_prefix"
      :header="tt('columns.prefix')"
      :show-filter-menu="false"
      style="min-width: 9rem"
    >
      <template #body="{ data }: { data: TokenSummary }">
        <span class="prefix-cell">{{ data.token_prefix }}…</span>
      </template>
      <template #filter>
        <InputText
          v-model="prefixFilter"
          :aria-label="t('common.filterBy', { column: tt('columns.prefix') })"
          size="small"
          fluid
        />
      </template>
    </Column>

    <!-- The permission tags are long labels that wrap, so this column needs a
         floor rather than the content-minimum the trailing spacer would
         otherwise squeeze it down to. -->
    <Column :header="tt('columns.permissions')" style="min-width: 20rem">
      <template #body="{ data }: { data: TokenSummary }">
        <div class="permissions-tags">
          <Tag
            v-for="perm in data.permissions"
            :key="perm"
            :value="permissionLabel(t, perm)"
            :severity="permissionSeverity(perm)"
          />
        </div>
      </template>
    </Column>

    <Column
      field="created"
      :header="tt('columns.created')"
      :show-filter-menu="false"
      style="width: 13rem"
      sortable
    >
      <template #body="{ data }: { data: TokenSummary }">
        <UserDateCell
          v-if="resolveCreatorName"
          :date="data.created"
          :user-id="data.created_by_id"
          :name="data.created_by_id != null ? resolveCreatorName(data.created_by_id) : null"
        />
        <template v-else>{{ formatISODate(data.created) }}</template>
      </template>
      <template #filter>
        <DemandDateRangeFilter
          v-model="createdRange"
          :placeholder="tt('filters.dateRange')"
          @clear-click="createdRange = null"
        />
      </template>
    </Column>

    <Column
      column-key="expires"
      :header="tt('columns.expires')"
      :show-filter-menu="false"
      style="width: 12rem"
    >
      <template #filter>
        <Select
          v-model="expiryFilter"
          :options="expiryOptions"
          option-label="label"
          option-value="value"
          :aria-label="t('common.filterBy', { column: tt('columns.expires') })"
          show-clear
          size="small"
          fluid
        />
      </template>
      <template #body="{ data }: { data: TokenSummary }">
        <Tag v-if="data.expires_at === null" severity="warn" :value="tt('neverExpires')" />
        <Tag v-else-if="data.is_expired" severity="danger" :value="tt('expired')" />
        <span v-else>{{ formatISODateTime(data.expires_at) }}</span>
      </template>
    </Column>

    <Column style="width: 100%" />
  </DataTable>

  <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />

  <TokenUsageLogDialog
    v-model:visible="usageLogVisible"
    :token="usageLogToken"
    :api="api"
    :i18n-prefix="i18nPrefix"
  />
</template>

<style scoped lang="scss">
.permissions-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.name-cell {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.prefix-cell {
  font-family: monospace;
  font-size: var(--font-size-sm);
}
</style>
