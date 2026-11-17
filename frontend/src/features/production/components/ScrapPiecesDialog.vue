<script setup lang="ts">
// One dialog for both scrap entry points. From an order it is fixed to that
// order; from a lot it offers its internal and mixed positions, preselecting
// the one in progress or else the last with a completion, and an order
// selector when that position has several open orders.
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { HelpDrawer } from '@/shared/help'

import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import { productionErrorKey } from '../utils/productionErrors'
import { formatISODate } from '@/core/utils/dates'
import { usePrint } from '@/shared/print'
import { getLot } from '../api/getLot'
import { scrapProductionOrderPieces } from '../api/scrapProductionOrderPieces'
import { scrapLotPieces } from '../api/scrapLotPieces'
import { SCRAP_REASONS, scrapReasonLabelKey } from '@/shared/utils/scrapReasons'

import type { ProductionOrderResponse } from '../types/productionOrdersResponse'
import type {
  LotPositionResponse,
  LotPositionProductionOrderSummary,
  LotResponse,
  ScrapPiecesResponse,
} from '../types/productionLotsResponse'
import type { ScrapReason } from '@/shared/utils/scrapReasons'
import { bySequence } from '../utils/sequence'
import { localizeLabel } from '@/shared/utils/localizeLabel'

// 'order': fixed to a known order, no step selector. 'lot': resolves a
// position (and, when ambiguous, an order) from the lot's own routing.
export type ScrapDialogTarget =
  | { kind: 'order'; order: ProductionOrderResponse }
  | { kind: 'lot'; lotId: number }

// Opened imperatively through open(), so no v-model.
const visible = ref(false)

const emit = defineEmits<{
  scrapped: [result: ScrapPiecesResponse]
}>()

const { t } = useI18n()
// Opens the handbook page that explains this dialog.
const explainVisible = ref(false)
// Prefixes the ids that tie each label to its control.
const uid = useId()
const toast = useAppToast()
const printService = usePrint()

const target = ref<ScrapDialogTarget | null>(null)
const loadingLot = ref(false)
const originLot = ref<LotResponse | null>(null)

const selectedPositionId = ref<number | null>(null)
const selectedOrderId = ref<number | null>(null)

const quantity = ref<number | null>(1)
const reason = ref<ScrapReason | null>(null)
const note = ref('')
const createReplacement = ref(true)
// On only when the scrap_tag classifier has a default printer, so the print
// would succeed.
const printScrapTag = ref(false)
const submitting = ref(false)
const errorMessage = ref<string | null>(null)

const internalPositions = computed<LotPositionResponse[]>(() => {
  if (target.value?.kind !== 'lot') return []
  return (originLot.value?.positions ?? [])
    .filter((p) => p.kind === 'internal' || p.kind === 'mixed')
    .slice()
    .sort(bySequence)
})

const selectedPosition = computed<LotPositionResponse | null>(
  () => internalPositions.value.find((p) => p.id === selectedPositionId.value) ?? null,
)

const openOrdersForPosition = computed<LotPositionProductionOrderSummary[]>(() =>
  (selectedPosition.value?.production_orders ?? []).filter(
    (o) => o.status !== 'completed' && o.status !== 'canceled',
  ),
)

const showOrderSelect = computed(
  () => target.value?.kind === 'lot' && openOrdersForPosition.value.length > 1,
)

const resolvedOrderId = computed<number | null>(() =>
  target.value?.kind === 'order' ? target.value.order.id : selectedOrderId.value,
)

const maxQuantity = computed<number | null>(() => {
  if (target.value?.kind === 'order') {
    return target.value.order.quantity - target.value.order.quantity_completed
  }
  const order = openOrdersForPosition.value.find((o) => o.id === selectedOrderId.value)
  return order ? order.quantity - order.quantity_completed : null
})

// Clamps when the cap shrinks below the input, never raises it.
watch(maxQuantity, (max) => {
  if (max !== null && quantity.value !== null && quantity.value > max) {
    quantity.value = max > 0 ? max : null
  }
})

const previewDate = computed(() =>
  originLot.value?.required_delivery_date ? formatISODate(originLot.value.required_delivery_date) : null,
)

const canSubmit = computed(() => {
  if (loadingLot.value || submitting.value) return false
  if (!originLot.value) return false
  if (!reason.value) return false
  if (quantity.value === null || quantity.value <= 0) return false
  if (maxQuantity.value !== null && quantity.value > maxQuantity.value) return false
  if (target.value?.kind === 'lot') {
    if (!selectedPositionId.value) return false
    if (!resolvedOrderId.value) return false
  }
  return true
})

function positionMethodLabel(position: LotPositionResponse): string {
  const names = (position.steps ?? []).map((s) =>
    localizeLabel(s.role === 'inspection' ? s.inspection_method_name : s.fabrication_method_name),
  )
  const joined = [...new Set(names)].filter(Boolean).join(', ')
  return joined || t('production.scrap.positionOptionNoMethod')
}

const positionOptions = computed(() =>
  internalPositions.value.map((p) => ({
    label: t('production.scrap.positionOption', {
      sequence: p.sequence,
      method: positionMethodLabel(p),
      completed: p.quantity_completed,
      quantity: p.quantity,
    }),
    value: p.id,
  })),
)

const orderOptions = computed(() =>
  openOrdersForPosition.value.map((o) => ({
    label: t('production.scrap.orderOption', {
      number: o.production_order_number,
      completed: o.quantity_completed,
      quantity: o.quantity,
    }),
    value: o.id,
  })),
)

const reasonOptions = computed(() =>
  SCRAP_REASONS.map((r) => ({ label: t(scrapReasonLabelKey(r)), value: r })),
)

function selectPosition(positionId: number | null): void {
  selectedPositionId.value = positionId
  const position = internalPositions.value.find((p) => p.id === positionId) ?? null
  const openOrders = (position?.production_orders ?? []).filter(
    (o) => o.status !== 'completed' && o.status !== 'canceled',
  )
  selectedOrderId.value = openOrders.length === 1 ? (openOrders[0]?.id ?? null) : null
}

async function open(next: ScrapDialogTarget): Promise<void> {
  target.value = next
  quantity.value = 1
  reason.value = null
  note.value = ''
  createReplacement.value = true
  printScrapTag.value = false
  errorMessage.value = null
  selectedPositionId.value = null
  selectedOrderId.value = null
  originLot.value = null
  visible.value = true

  const lotId = next.kind === 'lot' ? next.lotId : next.order.lot_id
  loadingLot.value = true
  try {
    originLot.value = await getLot(lotId)
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('production.scrap.errors.loadFailed')
  } finally {
    loadingLot.value = false
  }

  try {
    printScrapTag.value = await printService.hasDefaultPrinter('scrap_tag')
  } catch {
    printScrapTag.value = false
  }

  if (next.kind === 'lot') {
    const positions = internalPositions.value
    const inProgress = positions.find((p) => p.status === 'in_progress')
    const lastWithCompletion = [...positions].reverse().find((p) => p.quantity_completed > 0)
    const preselected = inProgress ?? lastWithCompletion ?? positions[0] ?? null
    selectPosition(preselected?.id ?? null)
  }
}

// Runs after the booking succeeded, so a print failure gets its own toast
// and never looks like the booking failed.
async function printScrapTagFor(result: ScrapPiecesResponse): Promise<void> {
  try {
    const job = await printService.printLotScrapTag(result.lot.id)
    if (job.status !== 'sent') {
      toast.error(result.lot.lot_number, job.error_message ?? t('production.scrap.printFailedToast'))
    }
  } catch (e) {
    toast.error(result.lot.lot_number, extractApiError(e) ?? t('production.scrap.printFailedToast'))
  }
}

async function onSubmit(): Promise<void> {
  if (!target.value || !canSubmit.value || quantity.value === null || !reason.value) return
  // The lot as read when the dialog opened; one changed since answers 409.
  const lot = originLot.value
  if (!lot) return

  submitting.value = true
  errorMessage.value = null
  try {
    const base = {
      quantity: quantity.value,
      reason: reason.value,
      note: note.value.trim() || undefined,
      create_replacement: createReplacement.value,
    }
    const result =
      target.value.kind === 'order'
        ? await scrapProductionOrderPieces(target.value.order.id, {
            ...base,
            expected_edit_version: target.value.order.edit_version,
            expected_lot_edit_version: lot.edit_version,
          })
        : await scrapLotPieces(target.value.lotId, {
            ...base,
            position_id: selectedPositionId.value!,
            production_order_id: resolvedOrderId.value,
            expected_edit_version: lot.edit_version,
          })

    visible.value = false
    emit('scrapped', result)

    if (result.created_lots?.length) {
      const lots = result.created_lots
        .map((l) => t('production.scrap.createdLot', { lotNumber: l.lot_number }))
        .join(', ')
      toast.success(t('production.scrap.createdLotsToast', { lots }))
    } else if (!createReplacement.value) {
      toast.success(t('production.scrap.recordedNoReplacementToast'))
    } else {
      toast.success(t('production.scrap.recordedToast'))
    }

    if (printScrapTag.value) {
      await printScrapTagFor(result)
    }
  } catch (e) {
    const key = productionErrorKey(e)
    errorMessage.value = key ? t(key) : (extractApiError(e) ?? t('production.scrap.errors.unknown'))
  } finally {
    submitting.value = false
  }
}

defineExpose({
  open,
  target,
  quantity,
  reason,
  note,
  createReplacement,
  printScrapTag,
  selectedPositionId,
  selectedOrderId,
  selectPosition,
  canSubmit,
  maxQuantity,
  positionOptions,
  orderOptions,
  showOrderSelect,
  openOrdersForPosition,
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <template #header>
      <div class="scrap-header">
        <span class="p-dialog-title">{{ t('production.scrap.title') }}</span>
        <Button
          type="button"
          class="scrap-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('production.scrap.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('production.scrap.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <div class="scrap-form">
      <template v-if="target?.kind === 'lot'">
        <div class="field">
          <label :id="`${uid}-position-label`" :for="`${uid}-position`">{{ t('production.scrap.position') }} *</label>
          <Select
            :input-id="`${uid}-position`"
            :aria-labelledby="`${uid}-position-label`"
            :model-value="selectedPositionId"
            @update:model-value="selectPosition"
            :options="positionOptions"
            option-label="label"
            option-value="value"
            :loading="loadingLot"
            :placeholder="t('production.scrap.positionPlaceholder')"
            fluid
          />
        </div>
        <div v-if="showOrderSelect" class="field">
          <label :id="`${uid}-order-label`" :for="`${uid}-order`">{{ t('production.scrap.order') }} *</label>
          <Select
            v-model="selectedOrderId"
            :input-id="`${uid}-order`"
            :aria-labelledby="`${uid}-order-label`"
            :options="orderOptions"
            option-label="label"
            option-value="value"
            fluid
          />
        </div>
        <Message
          v-else-if="selectedPositionId && !loadingLot && openOrdersForPosition.length === 0"
          severity="warn"
          :closable="false"
        >
          {{ t('production.scrap.noOpenOrder') }}
        </Message>
      </template>

      <div class="field">
        <label :for="`${uid}-quantity`">{{ t('production.scrap.quantity') }} *</label>
        <InputNumber
          v-model="quantity"
          :input-id="`${uid}-quantity`"
          :min="1"
          :max="maxQuantity ?? undefined"
          :max-fraction-digits="0"
          fluid
        />
        <p v-if="maxQuantity !== null" class="field-hint">
          {{ t('production.scrap.maxHint', { max: maxQuantity }) }}
        </p>
      </div>

      <div class="field">
        <label :id="`${uid}-reason-label`" :for="`${uid}-reason`">{{ t('production.scrap.reason') }} *</label>
        <Select
          v-model="reason"
          :input-id="`${uid}-reason`"
          :aria-labelledby="`${uid}-reason-label`"
          :options="reasonOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('production.scrap.reasonPlaceholder')"
          fluid
        />
      </div>

      <div class="field">
        <label :for="`${uid}-note`">{{ t('production.scrap.note') }}</label>
        <Textarea v-model="note" :id="`${uid}-note`" rows="2" auto-resize fluid />
      </div>

      <label class="checkbox-toggle">
        <Checkbox v-model="createReplacement" binary />
        <span>{{ t('production.scrap.createReplacement') }}</span>
      </label>

      <label class="checkbox-toggle">
        <Checkbox v-model="printScrapTag" binary />
        <span>{{ t('production.scrap.printScrapTag') }}</span>
      </label>

      <Message v-if="createReplacement && quantity" severity="info" :closable="false">
        {{
          previewDate
            ? t('production.scrap.previewWithDate', { n: quantity, date: previewDate })
            : t('production.scrap.preview', { n: quantity })
        }}
      </Message>
      <Message v-else-if="!createReplacement" severity="info" :closable="false">
        {{ t('production.scrap.previewNoReplacement') }}
      </Message>

      <Message v-if="errorMessage" severity="error" :closable="false">
        {{ errorMessage }}
      </Message>
    </div>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="submitting"
        @click="visible = false"
      />
      <Button
        :label="t('production.scrap.submit')"
        :loading="submitting"
        :disabled="!canSubmit"
        @click="onSubmit"
      />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="production/lot-lifecycle" anchor="scrapped" />
</template>

<style scoped lang="scss">
.scrap-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.scrap-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.scrap-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.field-hint {
  margin: 0;
  font-weight: 400;
}

.checkbox-toggle {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}
</style>
