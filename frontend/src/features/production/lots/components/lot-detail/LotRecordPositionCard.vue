<script setup lang="ts">
// Record card of one lot position: its header fields, steps, the external
// order or contributing production orders, QA evidence and the position's
// event history. Order and file details open in dialogs from here.
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import { formatBytes } from '@/core/utils/bytes'
import { formatDecimal } from '@/core/utils/numbers'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import { OrderDetailDialog } from '@/features/orders'
import { getProductionOrderFileBlob } from '../../../api/getProductionOrderFileBlob'
import { lotEventActorName, lotEventIcon, lotEventLabel } from '../../utils/lotEventLabels'
import {
  formatDurationBetween,
  formatMinutesDuration,
  stepMethodLabel,
} from '../../../utils/lotStepDisplay'
import { buildTimeComparison } from '../../utils/timeComparison'
import {
  lotPositionKindSeverity,
  lotPositionStatusKey,
  lotPositionStatusSeverityFor,
} from '../../../utils/lotStatus'
import ProductionOrderDetailDialog from '../ProductionOrderDetailDialog.vue'
import LotPositionStepsTable from './LotPositionStepsTable.vue'
import LotPositionExternalOrder from './LotPositionExternalOrder.vue'
import LotProductionOrderRecord from './LotProductionOrderRecord.vue'
import ReverseCompletionDialog from './ReverseCompletionDialog.vue'

import type {
  LotEventResponse,
  LotPositionProvisionResponse,
  LotPositionResponse,
} from '../../../types/productionLotsResponse'
import type {
  ManufacturingAssessmentResponse,
  ProductionOrderCompletionResponse,
  ProductionOrderFile,
  ProductionOrderResponse,
} from '../../../types/productionOrdersResponse'
import type { OrderItemResponse, OrderResponse } from '@/features/orders'
import { sortedBySequence } from '../../../utils/sequence'

const props = defineProps<{
  position: LotPositionResponse
  orders: ProductionOrderResponse[]
  provisions: LotPositionProvisionResponse[]
  orderItem: OrderItemResponse | null
  order: OrderResponse | null
  events: LotEventResponse[]
  assessmentForOrder: (orderId: number) => ManufacturingAssessmentResponse | null
  filesForOrder: (orderId: number) => ProductionOrderFile[]
}>()

const { t, te } = useI18n()
const { missing } = useMissingPermission()

// The evidence is not loaded without the right to read it, so the card says
// which permission is missing instead of claiming nothing was uploaded.
const evidenceBlocked = computed(() => missing(Permission.WRITE_INSPECTIONS))

// Evidence only exists for inspection positions.
const hasInspectionStep = computed(() =>
  (props.position.steps ?? []).some((s) => s.role === 'inspection'),
)

const evidenceRequired = computed(() =>
  (props.position.steps ?? []).some((s) => s.inspection_method_requires_evidence),
)

// One flat list across the position's orders: a split position can hold
// evidence on more than one, so each row keeps its order number.
const evidenceRows = computed(() =>
  props.orders.flatMap((order) =>
    props.filesForOrder(order.id).map((file) => ({ order, file })),
  ),
)

const showReverseCompletion = ref(false)
const reversingOrder = ref<ProductionOrderResponse | null>(null)
const reversingCompletion = ref<ProductionOrderCompletionResponse | null>(null)

function openReverseCompletion(
  order: ProductionOrderResponse,
  completion: ProductionOrderCompletionResponse,
): void {
  reversingOrder.value = order
  reversingCompletion.value = completion
  showReverseCompletion.value = true
}

const showFilePreview = ref(false)
const previewFile = ref<ProductionOrderFile | null>(null)
const previewFetch = ref<() => Promise<Blob>>(() => Promise.reject(new Error('no file')))

function openEvidencePreview(orderId: number, file: ProductionOrderFile): void {
  previewFile.value = file
  previewFetch.value = () => getProductionOrderFileBlob(orderId, file.id)
  showFilePreview.value = true
}

const sortedSteps = computed(() =>
  sortedBySequence(props.position.steps),
)

// De-duplicated, since steps can repeat a method.
const fabricationMethodsLabel = computed(() =>
  [...new Set(sortedSteps.value.map((s) => stepMethodLabel(s)))].join(', '),
)

const isExternal = computed(
  () => props.position.kind === 'external' || props.position.kind === 'mixed',
)
const isInternal = computed(
  () => props.position.kind === 'internal' || props.position.kind === 'mixed',
)

const relevantEvents = computed(() => {
  const stepIds = new Set((props.position.steps ?? []).map((s) => s.id))
  const orderIds = new Set(props.orders.map((o) => o.id))
  return props.events
    .filter(
      (e) =>
        (e.entity === 'position' && e.entity_id === props.position.id) ||
        (e.entity === 'step' && e.entity_id !== null && stepIds.has(e.entity_id)) ||
        (e.entity === 'order' && e.entity_id !== null && orderIds.has(e.entity_id)),
    )
    .sort((a, b) => a.occurred_at.localeCompare(b.occurred_at))
})

// Only the order_started event records who started an order; the latest
// match wins, since a resumed order starts more than once.
function startedByFor(order: ProductionOrderResponse): string | null {
  const startedEvents = relevantEvents.value.filter(
    (e) => e.entity === 'order' && e.entity_id === order.id && e.event_type === 'order_started',
  )
  const last = startedEvents[startedEvents.length - 1]
  return last ? lotEventActorName(last) : null
}

// Completions are stored in order, so once the order is completed the last
// one finished it.
function endedByFor(order: ProductionOrderResponse): string | null {
  if (order.status !== 'completed' || (order.completions?.length ?? 0) === 0) return null
  const completions = order.completions!
  const last = completions[completions.length - 1]
  if (!last) return null
  return (last.recorded_by ?? last.operator)?.full_name ?? null
}

function durationFor(order: ProductionOrderResponse): string | null {
  if (!order.actual_start || !order.actual_end) return null
  return formatDurationBetween(order.actual_start, order.actual_end)
}

const enrichedOrders = computed(() =>
  props.orders.map((order) => {
    const assessment = props.assessmentForOrder(order.id)
    return {
      order,
      startedBy: startedByFor(order),
      endedBy: endedByFor(order),
      duration: durationFor(order),
      estimate: formatMinutesDuration(order.estimated_duration_minutes),
      assessment,
      comparison: buildTimeComparison({
        steps: props.position.steps ?? [],
        orderQuantity: order.quantity,
        estimatedDurationMinutes: order.estimated_duration_minutes,
        assessment,
      }),
    }
  }),
)

const showOrderDetail = ref(false)
const orderDetailOrderId = ref<number | null>(null)

function openOrderDetail(orderId: number | null): void {
  if (orderId === null) return
  orderDetailOrderId.value = orderId
  showOrderDetail.value = true
}

const showProductionOrderDetail = ref(false)
const productionOrderDetailTarget = ref<ProductionOrderResponse | null>(null)

function openProductionOrderDetail(order: ProductionOrderResponse): void {
  productionOrderDetailTarget.value = order
  showProductionOrderDetail.value = true
}

const productionOrderDetailStartedBy = computed(() =>
  productionOrderDetailTarget.value ? startedByFor(productionOrderDetailTarget.value) : null,
)
const productionOrderDetailEndedBy = computed(() =>
  productionOrderDetailTarget.value ? endedByFor(productionOrderDetailTarget.value) : null,
)
const productionOrderDetailDuration = computed(() =>
  productionOrderDetailTarget.value ? durationFor(productionOrderDetailTarget.value) : null,
)
const productionOrderDetailAssessment = computed(() =>
  productionOrderDetailTarget.value
    ? props.assessmentForOrder(productionOrderDetailTarget.value.id)
    : null,
)
</script>

<template>
  <div class="position-card">
    <div class="position-card-header">
      <div class="header-title-line">
        <span class="position-seq">#{{ position.sequence }}</span>
        <span v-if="fabricationMethodsLabel" class="position-method">{{
          fabricationMethodsLabel
        }}</span>
      </div>
      <div class="header-fields">
        <span class="field-label">{{ t('production.lots.detail.record.execution.source') }}</span>
        <Tag
          :value="t(`production.lots.positionKind.${position.kind}`)"
          :severity="lotPositionKindSeverity[position.kind]"
        />

        <span class="field-label">{{ t('production.lots.detail.record.execution.status') }}</span>
        <Tag
          :value="
            t(
              `production.lots.positionStatus.${lotPositionStatusKey(position.status, position.kind)}`,
            )
          "
          :severity="lotPositionStatusSeverityFor(position.status, position.kind)"
        />

        <span class="field-label">{{ t('production.lots.detail.record.execution.qty') }}</span>
        <span class="position-progress"
          >{{ formatDecimal(position.quantity_completed) }} /
          {{ formatDecimal(position.quantity) }}</span
        >

        <span class="field-label">{{
          t('production.lots.detail.record.execution.uncommitted')
        }}</span>
        <span
          class="position-progress"
          v-tooltip.top="t('production.lots.detail.record.execution.uncommittedTooltip')"
          >{{ formatDecimal(position.quantity_remaining) }}</span
        >
      </div>
      <div v-if="position.note" class="position-note">{{ position.note }}</div>
    </div>

    <div class="position-card-body">
      <LotPositionStepsTable :steps="sortedSteps" :quantity="position.quantity" />

      <LotPositionExternalOrder
        v-if="isExternal"
        :position="position"
        :provisions="provisions"
        :order-item="orderItem"
        :order="order"
        @open-order="openOrderDetail"
      />

      <div v-if="isInternal" class="sub-section">
        <span class="section-label">
          {{ t('production.lots.detail.record.execution.contributingOrders') }}
          <template v-if="orders.length > 1">
            {{ t('production.lots.detail.record.execution.splitAcross', { count: orders.length }) }}
          </template>
        </span>
        <div v-if="orders.length === 0" class="empty-note">
          {{ t('production.lots.detail.record.execution.notAssigned') }}
        </div>
        <LotProductionOrderRecord
          v-for="row in enrichedOrders"
          :key="row.order.id"
          :row="row"
          @open="openProductionOrderDetail"
          @reverse="openReverseCompletion"
        />
      </div>

      <div v-if="hasInspectionStep && isInternal" class="sub-section">
        <span class="section-label">
          {{ t('production.lots.detail.record.execution.evidence')
          }}<template v-if="!evidenceBlocked"> ({{ evidenceRows.length }})</template>
        </span>
        <div v-if="evidenceBlocked" class="empty-note">
          <i class="mdi mdi-lock-outline" aria-hidden="true" />
          {{ evidenceBlocked }}
        </div>
        <div v-else-if="evidenceRows.length" class="evidence-list">
          <div v-for="row in evidenceRows" :key="row.file.id" class="evidence-row">
            <i class="mdi mdi-file-document-outline" aria-hidden="true" />
            <button
              type="button"
              class="evidence-link"
              @click="openEvidencePreview(row.order.id, row.file)"
            >
              {{ row.file.file_name }}
            </button>
            <span class="field-sublabel">{{ formatBytes(row.file.size_bytes) }}</span>
            <span v-if="orders.length > 1" class="field-sublabel">
              {{ row.order.production_order_number }}
            </span>
          </div>
        </div>
        <div v-else class="empty-note" :class="{ 'evidence-missing': evidenceRequired }">
          <i v-if="evidenceRequired" class="mdi mdi-alert-outline" aria-hidden="true" />
          {{ t('production.lots.detail.record.execution.evidenceMissing') }}
        </div>
      </div>

      <div class="sub-section history-section">
        <span class="section-label">
          {{ t('production.lots.detail.record.execution.history') }} ({{ relevantEvents.length }})
        </span>
        <div class="history-table-wrap">
          <table class="history-table">
            <tbody>
              <tr v-for="event in relevantEvents" :key="event.id">
                <td class="history-icon-cell">
                  <i class="mdi" :class="lotEventIcon(event.event_type)" aria-hidden="true" />
                </td>
                <td class="history-event-cell">{{ lotEventLabel(event.event_type, { t, te }) }}</td>
                <td class="history-date-cell">{{ formatISODateTime(event.occurred_at) }}</td>
                <td>
                  {{ lotEventActorName(event) }}
                </td>
              </tr>
              <tr v-if="relevantEvents.length === 0">
                <td colspan="4" class="empty-note">
                  {{ t('production.lots.detail.audit.empty') }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <OrderDetailDialog v-model:visible="showOrderDetail" :order-id="orderDetailOrderId" />
    <ProductionOrderDetailDialog
      v-model:visible="showProductionOrderDetail"
      :order="productionOrderDetailTarget"
      :started-by="productionOrderDetailStartedBy"
      :ended-by="productionOrderDetailEndedBy"
      :duration="productionOrderDetailDuration"
      :assessment="productionOrderDetailAssessment"
    />
    <FilePreviewDialog
      v-if="previewFile"
      v-model:visible="showFilePreview"
      :filename="previewFile.file_name"
      :mime-type="previewFile.mime_type"
      :fetch-blob="previewFetch"
    />
    <ReverseCompletionDialog
      v-model:visible="showReverseCompletion"
      :order="reversingOrder"
      :completion="reversingCompletion"
    />
  </div>
</template>

<style scoped lang="scss">
// Fixed width instead of stretching to the tallest sibling, since positions
// in the strip carry very different amounts of content.
.position-card {
  flex: 0 0 22rem;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  background: var(--p-content-background);
}

.position-card-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
}

.header-title-line {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-weight: 700;
}

// Label and value columns, so the header fields read as a small table.
.header-fields {
  display: grid;
  grid-template-columns: auto auto;
  align-items: center;
  justify-items: start;
  column-gap: var(--space-2);
  row-gap: var(--space-1);
  width: fit-content;
}

.position-method {
  font-size: var(--font-size-sm);
}

.position-progress {
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
}

.position-card-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: 0 var(--space-3) var(--space-3);
}

.section-label {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

.sub-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.field-sublabel {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.empty-note {
  font-style: italic;
}

.evidence-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.evidence-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.evidence-link {
  background: none;
  border: 0;
  padding: 0;
  font: inherit;
  font-size: var(--font-size-sm);
  color: var(--p-primary-color);
  cursor: pointer;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;

  &:hover {
    text-decoration: underline;
  }
}

.evidence-missing {
  color: var(--p-orange-600);
}

.position-note {
  font-size: var(--font-size-sm);
  color: var(--p-text-color);
  white-space: pre-line;
  padding-top: var(--space-1);
}

.history-table-wrap {
  overflow-y: auto;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  max-height: 9rem;
}

.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-xs);

  td {
    padding: var(--space-1) var(--space-2);
    border-bottom: 1px solid var(--p-content-border-color);
    color: var(--p-text-muted-color);
  }

  tr:last-child td {
    border-bottom: none;
  }
}

.history-icon-cell {
  width: 1.4rem;

  i {
    color: var(--p-text-muted-color);
  }
}

.history-event-cell {
  color: var(--p-text-color);
  font-weight: 500;
}

.history-date-cell {
  white-space: nowrap;
}
</style>
