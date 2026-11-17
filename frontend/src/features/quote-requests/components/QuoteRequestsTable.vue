<script setup lang="ts">
// The quote requests, built like the orders table: one page from the server,
// filters in the header row, and a row that expands into its lines. The
// columns are as wide as their content; the note takes what is left.
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { FilterMatchMode } from '@openvue/core/api'

import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useRowOpenGuard } from '@/core/composables/useRowOpenGuard'
import { useServerTable } from '@/core/composables/useServerTable'
import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatPrice } from '@/core/utils/currency'
import { formatDateOrDash } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { SupplierSearchFilter } from '@/features/suppliers'
import EmptyState from '@/shared/components/EmptyState.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import { useQuoteRequestsStore } from '../stores/quoteRequestsStore'
import { OPEN_QUOTE_REQUEST_STATUSES, quoteRequestStatusSeverity } from '../utils/quoteRequestFormat'
import QuoteRequestLinesTable from './QuoteRequestLinesTable.vue'
import { AgentBadge } from '@/features/agents'
import type { DataTableFilterMeta, DataTableRowClickEvent } from 'openvue/datatable'
import type { QuoteRequestFilterParams } from '../types/quoteRequestsRequest'
import type { QuoteRequestResponse, QuoteRequestStatus } from '../types/quoteRequestsResponse'

const props = defineProps<{
  /** Closed and canceled requests are listed too. */
  showClosed: boolean
}>()

const { t } = useI18n()
const store = useQuoteRequestsStore()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
watchLoadingBar(computed(() => store.loading))

// Filtering is server-side; this object only exists because
// filterDisplay="row" throws without an entry per filterable column.
const FILTERS: DataTableFilterMeta = {
  request_number: { value: null, matchMode: FilterMatchMode.CONTAINS },
  status: { value: null, matchMode: FilterMatchMode.EQUALS },
  suppliers: { value: null, matchMode: FilterMatchMode.EQUALS },
}

const STATUSES: QuoteRequestStatus[] = ['draft', 'sent', 'awarded', 'closed', 'canceled']
const statusOptions = computed(() =>
  STATUSES.map((value) => ({ value, label: t(`quoteRequests.status.${value}`) })),
)

const searchFilter = ref('')
const statusFilter = ref<QuoteRequestStatus[]>([])
const supplierFilter = ref<number | null>(null)

function statuses(): QuoteRequestStatus[] | undefined {
  if (statusFilter.value.length > 0) return statusFilter.value
  return props.showClosed ? undefined : [...OPEN_QUOTE_REQUEST_STATUSES]
}

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: ({ first: skip, rows: limit }): QuoteRequestFilterParams => ({
    skip,
    limit,
    status: statuses(),
    search: searchFilter.value.trim() || undefined,
    supplier_id: supplierFilter.value ?? undefined,
  }),
  fetch: (params) => store.refresh(params),
})

fetchItems()
watch(searchFilter, resetAndFetchDebounced)
watch([statusFilter, supplierFilter, () => props.showClosed], resetAndFetch)
useLiveRefresh([LiveResource.QUOTE_REQUESTS], fetchItems)

const hasActiveFilters = computed(
  () => !!searchFilter.value || statusFilter.value.length > 0 || supplierFilter.value !== null,
)

function clearFilters(): void {
  searchFilter.value = ''
  statusFilter.value = []
  supplierFilter.value = null
}

// ── Row expansion ─────────────────────────────────────────────────────

const expandedRows = ref<Record<string, boolean>>({})
const { guard } = useRowOpenGuard<number>()

function toggle(request: QuoteRequestResponse): void {
  const id = String(request.id)
  const next = { ...expandedRows.value }
  if (next[id]) delete next[id]
  else next[id] = true
  expandedRows.value = next
}

function onRowClick(event: DataTableRowClickEvent): void {
  const request = event.data as QuoteRequestResponse
  guard(request.id, () => toggle(request))
}

// ── Cells ─────────────────────────────────────────────────────────────

function suppliersOf(request: QuoteRequestResponse): string {
  return request.suppliers.map((s) => s.supplier_name).join(', ')
}

/** The lowest total of an offer that prices every line, extra costs included. */
function bestTotal(request: QuoteRequestResponse): number | null {
  const row = request.suppliers.find((s) => s.id === request.cheapest_complete_supplier_id)
  return row ? row.total : null
}

function awardedCount(request: QuoteRequestResponse): number {
  return request.lines.filter((line) => line.state === 'awarded').length
}

defineExpose({ hasActiveFilters, clearFilters, fetchItems })
</script>

<template>
  <DataTable
    :value="store.items"
    data-key="id"
    lazy
    paginator
    :total-records="store.total"
    :first="first"
    :rows="rows"
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    filter-display="row"
    :filters="FILTERS"
    scrollable
    scroll-height="flex"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    size="small"
    v-model:expanded-rows="expandedRows"
    selection-mode="single"
    class="phone-columns clickable-rows"
    data-testid="quote-requests-table"
    @page="onPage"
    @row-click="onRowClick"
  >
    <template #empty>
      <EmptyState :message="t('quoteRequests.list.empty')" icon="mdi mdi-scale-balance" />
    </template>

    <Column expander class="column-fit" />

    <Column header="#" class="column-fit phone-row-number" body-class="row-number">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>

    <Column
      field="request_number"
      :header="t('quoteRequests.list.columns.number')"
      class="column-fit phone-col"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: QuoteRequestResponse }">
        <!-- .stop so opening the request doesn't also toggle the row. -->
        <RouterLink class="number-link" :to="`/procurement/quotes/${data.id}`" @click.stop>
          <strong>{{ data.request_number }}</strong>
        </RouterLink>
        <AgentBadge kind="quote_request" :public-id="data.public_id" />
      </template>
      <template #filter>
        <InputText
          v-model="searchFilter"
          :placeholder="t('quoteRequests.list.filterBy')"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="status"
      :header="t('quoteRequests.list.columns.status')"
      class="column-fit phone-col"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: QuoteRequestResponse }">
        <Tag
          :value="t(`quoteRequests.status.${data.status}`)"
          :severity="quoteRequestStatusSeverity(data.status)"
        />
      </template>
      <template #filter>
        <MultiSelect
          v-model="statusFilter"
          :aria-label="t('quoteRequests.list.columns.status')"
          :options="statusOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('quoteRequests.list.any')"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="suppliers"
      :header="t('quoteRequests.list.columns.suppliers')"
      class="column-fit"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: QuoteRequestResponse }">
        <span :class="{ muted: data.suppliers.length === 0 }">
          {{ suppliersOf(data) || getEmptyPlaceholder() }}
        </span>
      </template>
      <template #filter>
        <SupplierSearchFilter v-model="supplierFilter" :placeholder="t('quoteRequests.list.any')" />
      </template>
    </Column>

    <Column :header="t('quoteRequests.list.columns.lines')" class="column-fit" body-class="num-cell">
      <template #body="{ data }: { data: QuoteRequestResponse }">
        {{ awardedCount(data) }} / {{ data.lines.length }}
      </template>
    </Column>

    <Column :header="t('quoteRequests.list.columns.bestTotal')" class="column-fit" body-class="num-cell">
      <template #body="{ data }: { data: QuoteRequestResponse }">
        <span :class="{ muted: bestTotal(data) === null }">{{ formatPrice(bestTotal(data)) }}</span>
      </template>
    </Column>

    <Column :header="t('quoteRequests.list.columns.deadline')" class="column-fit phone-col">
      <template #body="{ data }: { data: QuoteRequestResponse }">
        <span :class="{ muted: !data.deadline }">
          {{ data.deadline ? formatDateOrDash(data.deadline) : getEmptyPlaceholder() }}
        </span>
      </template>
    </Column>

    <Column :header="t('quoteRequests.list.columns.created')" class="column-fit">
      <template #body="{ data }: { data: QuoteRequestResponse }">
        <UserDateCell :date="data.created" :user="data.creator" />
      </template>
    </Column>

    <!-- The free-text column takes the width the others leave. -->
    <Column :header="t('quoteRequests.list.columns.note')">
      <template #body="{ data }: { data: QuoteRequestResponse }">
        <span :class="{ muted: !data.note }">{{ data.note || getEmptyPlaceholder() }}</span>
      </template>
    </Column>

    <template #expansion="{ data }: { data: QuoteRequestResponse }">
      <QuoteRequestLinesTable :request="data" />
    </template>
  </DataTable>
</template>

<style scoped lang="scss">
.number-link {
  color: inherit;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.muted {
  color: var(--p-text-muted-color);
}
</style>
