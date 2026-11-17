<script setup lang="ts">
// The Manage Quotes panel beside a demand or lot table: the selected rows
// become lines of a draft or sent quote request, with the share of each
// demand, but no supplier and no price. A share reserves nothing; the award
// allocates what the demand still needs then. The table that hosts the
// panel builds the rows from its selection and keeps them in `rows`.
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { roundTo } from '@/core/utils/numbers'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { useAppToast } from '@/core/composables/useAppToast'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { formatUnit } from '@/shared/utils/units'
import { addQuoteRequestLines } from '../api/addQuoteRequestLines'
import { getQuoteRequests } from '../api/getQuoteRequests'
import { OPEN_QUOTE_REQUEST_STATUSES } from '../utils/quoteRequestFormat'
import QuoteRequestCreateDialog from './QuoteRequestCreateDialog.vue'
import type { QuoteRequestLineRequest } from '../types/quoteRequestsRequest'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'
import type { QuotePanelRow } from '../utils/quotePanelRows'
import { quotePanelLines, rowSharesExceedLine, rowShowsShares } from '../utils/quotePanelRows'
import EmptyState from '@/shared/components/EmptyState.vue'
import { HelpButton } from '@/shared/help'

const props = withDefaults(
  defineProps<{
    selectedCount: number
    /** Suppliers the create dialog suggests first. */
    suggestedSupplierIds?: number[]
    /** Offers to leave a row out, for a host that lists every candidate. */
    removableRows?: boolean
    /** The handbook page the header's help button opens; without one the header has none. */
    helpSlug?: string
  }>(),
  { suggestedSupplierIds: () => [], removableRows: false, helpSlug: undefined },
)

const rows = defineModel<QuotePanelRow[]>('rows', { required: true })
const emit = defineEmits<{ added: [request: QuoteRequestResponse]; clear: [] }>()

defineOptions({ inheritAttrs: false })

const { t } = useI18n()
const toast = useAppToast()
const { toastOnError } = useErrorToast()
const { submitting, errorMessage, run } = useSubmitAction()

const requests = ref<QuoteRequestResponse[]>([])
const loadingRequests = ref(false)
const selectedRequest = ref<QuoteRequestResponse | null>(null)
const showCreate = ref(false)

async function loadRequests(): Promise<void> {
  loadingRequests.value = true
  try {
    const page = await getQuoteRequests({
      status: [...OPEN_QUOTE_REQUEST_STATUSES],
      limit: API_MAX_PAGE_SIZE,
    })
    requests.value = page.items
    if (selectedRequest.value) {
      selectedRequest.value =
        page.items.find((r) => r.id === selectedRequest.value?.id) ?? null
    }
  } finally {
    loadingRequests.value = false
  }
}

function requestLabel(request: QuoteRequestResponse): string {
  const suppliers = request.suppliers.map((s) => s.supplier_name).join(', ')
  return suppliers ? `${request.request_number} (${suppliers})` : request.request_number
}

const lines = computed<QuoteRequestLineRequest[]>(() => quotePanelLines(rows.value))

const canSubmit = computed(
  () =>
    !!selectedRequest.value &&
    rows.value.length > 0 &&
    rows.value.every((row) => row.quantity > 0 && !rowSharesExceedLine(row)),
)

function sharesTotal(row: QuotePanelRow): number {
  return roundTo(
    row.shares.reduce((sum, share) => sum + (share.quantity || 0), 0),
    6,
  )
}

function onShareChanged(row: QuotePanelRow): void {
  if (!row.quantityEdited) row.quantity = sharesTotal(row)
}

async function onSubmit(): Promise<void> {
  const target = selectedRequest.value
  if (!target) {
    errorMessage.value = t('quoteRequests.panel.errors.noRequest')
    return
  }
  const ok = await run(async () => {
    const saved = await addQuoteRequestLines(target.id, lines.value)
    toast.success(saved.request_number, t('quoteRequests.panel.added', { count: lines.value.length }))
    emit('added', saved)
  }, t('quoteRequests.panel.errors.unknown'))
  if (ok) await loadRequests().catch(toastOnError())
}

function onCreated(created: QuoteRequestResponse): void {
  requests.value = [created, ...requests.value]
  selectedRequest.value = created
}

onMounted(() => {
  loadRequests().catch(toastOnError())
})
</script>

<template>
  <Panel class="manage-quote-panel fill-panel" v-bind="$attrs">
    <template #header>
      <div class="panel-header-row">
        <div class="panel-header-main">
          <span class="panel-title">{{ t('quoteRequests.panel.title') }}</span>
          <Tag
            v-if="props.selectedCount > 0"
            :value="t('quoteRequests.panel.selectedCount', { count: props.selectedCount })"
            severity="secondary"
          />
        </div>
        <HelpButton v-if="props.helpSlug" :slug="props.helpSlug" size="small" rounded />
      </div>
    </template>

    <div class="request-section">
      <label id="manage-quote-request-label" class="field-label" for="manage-quote-request">
        {{ t('quoteRequests.panel.request') }}
      </label>
      <div class="request-select-row">
        <Select
          v-model="selectedRequest"
          input-id="manage-quote-request"
          aria-labelledby="manage-quote-request-label"
          :options="requests"
          :option-label="requestLabel"
          :loading="loadingRequests"
          :placeholder="t('quoteRequests.panel.selectRequest')"
          show-clear
          fluid
          size="small"
        />
        <Button
          icon="mdi mdi-refresh"
          severity="secondary"
          text
          rounded
          size="small"
          :loading="loadingRequests"
          v-tooltip.focus="t('quoteRequests.panel.refresh')"
          :aria-label="t('quoteRequests.panel.refresh')"
          @click="loadRequests().catch(toastOnError())"
        />
        <Button
          icon="mdi mdi-plus"
          severity="secondary"
          text
          rounded
          size="small"
          v-tooltip.focus="t('quoteRequests.panel.create')"
          :aria-label="t('quoteRequests.panel.create')"
          @click="showCreate = true"
        />
      </div>
    </div>

    <div class="rows-section">
      <EmptyState v-if="rows.length === 0" :message="t('quoteRequests.panel.noSelection')" icon="mdi mdi-checkbox-marked-outline" />
      <div v-else class="rows-list">
        <div v-for="row in rows" :key="row.key" class="row-card" data-testid="quote-panel-row">
          <div class="row-item">
            <div class="row-name-line">
              <span class="row-name">{{ row.title }}</span>
              <Button
                v-if="props.removableRows"
                icon="mdi mdi-close"
                severity="secondary"
                text
                rounded
                size="small"
                :aria-label="t('quoteRequests.panel.leaveOut')"
                v-tooltip.top="t('quoteRequests.panel.leaveOut')"
                @click="rows = rows.filter((r) => r.key !== row.key)"
              />
            </div>
            <span v-if="row.subtitle" class="row-sub">{{ row.subtitle }}</span>
            <span v-if="row.projectNumber" class="row-sub">{{ row.projectNumber }}</span>
          </div>
          <div class="row-qty">
            <InputNumber
              v-model="row.quantity"
              :min="0.001"
              :max="row.maxQuantity ?? undefined"
              :max-fraction-digits="3"
              :input-style="{ width: '6rem' }"
              size="small"
              @update:model-value="row.quantityEdited = true"
            />
            <span class="row-unit">{{ formatUnit(row.unit) }}</span>
          </div>
          <div v-if="rowShowsShares(row)" class="row-demands">
            <div v-for="share in row.shares" :key="share.demandId" class="row-demand">
              <span class="row-demand-label">
                {{ t('quoteRequests.panel.share', { id: share.demandId }) }}
              </span>
              <InputNumber
                v-model="share.quantity"
                :min="0"
                :max-fraction-digits="3"
                :input-style="{ width: '6rem' }"
                size="small"
                @update:model-value="onShareChanged(row)"
              />
              <span class="row-unit">{{ formatUnit(row.unit) }}</span>
            </div>
            <Message v-if="rowSharesExceedLine(row)" severity="warn" size="small" :closable="false">
              {{ t('quoteRequests.panel.sharesExceedLine') }}
            </Message>
          </div>
        </div>
      </div>
    </div>

    <div class="panel-footer">
      <Message v-if="errorMessage" severity="error" :closable="false" size="small">
        {{ errorMessage }}
      </Message>
      <Button
        :label="t('quoteRequests.panel.addToRequest')"
        icon="mdi mdi-scale-balance"
        :disabled="!canSubmit"
        :loading="submitting"
        fluid
        @click="onSubmit"
      />
      <Button
        v-if="props.selectedCount > 0"
        :label="t('quoteRequests.panel.clearSelection')"
        severity="secondary"
        outlined
        size="small"
        fluid
        @click="emit('clear')"
      />
    </div>
  </Panel>

  <QuoteRequestCreateDialog
    v-model:visible="showCreate"
    :suggested-supplier-ids="props.suggestedSupplierIds"
    @created="onCreated"
  />
</template>

<style scoped lang="scss">
.manage-quote-panel {
  flex: 0 0 auto;
  --fill-panel-gap: var(--space-3);
}

.panel-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-2);
}

// Title and count stay together on the left so the help button can hold the
// right edge.
.panel-header-main {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.request-section {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.field-label {
  padding-top: var(--space-3);
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.request-select-row {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.rows-section {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}



.rows-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.row-card {
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  padding: var(--space-2) var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.row-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-bottom: var(--space-2);
}

.row-name-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-1);
}

.row-name {
  font-weight: 600;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.row-sub {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.row-qty,
.row-demand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.row-demands {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.row-demand-label {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  min-width: 6rem;
}

.row-unit {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.panel-footer {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
</style>
