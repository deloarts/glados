<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { HelpDrawer } from '@/shared/help'
import { useAppToast } from '@/core/composables/useAppToast'

import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { dateToParam, toLocalDayStart, todayStart } from '@/core/utils/dates'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useProductionQueueStore } from '../stores/productionQueueStore'
import { useProductionOrderFilesStore } from '../stores/productionOrderFilesStore'
import { getProductionOrderFileBlob } from '../api/getProductionOrderFileBlob'
import { productionErrorKey } from '../utils/productionErrors'
import FilesSection from '@/shared/components/files/FilesSection.vue'
import { SCRAP_REASONS, scrapReasonLabelKey } from '@/shared/utils/scrapReasons'
import type { ScrapReason } from '@/shared/utils/scrapReasons'

import type { ProductionOrderResponse } from '../types/productionOrdersResponse'
import type { LotOriginDisposition, LotStepResponse } from '../types/productionLotsResponse'
import type { MultiCategorySpec } from '@/shared/components/files/fileCategorySpec'

const props = withDefaults(
  defineProps<{
    order: ProductionOrderResponse | null
    // The position's steps, only used to detect an inspection step. Without
    // one the plain completion form renders.
    steps?: LotStepResponse[]
  }>(),
  { steps: () => [] },
)

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  recorded: [order: ProductionOrderResponse]
}>()

const { t } = useI18n()
// Opens the handbook page that explains this dialog.
const explainVisible = ref(false)
// Prefixes the ids that tie each label to its control.
const uid = useId()
const toast = useAppToast()
const store = useProductionQueueStore()
const currentUserStore = useCurrentUserStore()
const { hasPermission } = usePermissions()
const filesStore = useProductionOrderFilesStore()

const MEASUREMENT_FILES: MultiCategorySpec[] = [
  {
    key: 'measurement_report',
    labelKey: 'productionQueue.completion.files.measurement_report',
    accent: 'teal',
    icon: 'mdi mdi-file-chart-outline',
    accept: 'application/pdf,image/*',
  },
]

// ── Inspection detection ────────────────────────────────────────────
const inspectionStep = computed(() => props.steps.find((s) => s.role === 'inspection') ?? null)
const isInspectionOrder = computed(() => inspectionStep.value !== null)
const requiresEvidence = computed(
  () => inspectionStep.value?.inspection_method_requires_evidence === true,
)
const canRecordInspection = computed(() => hasPermission(Permission.WRITE_INSPECTIONS))
const permissionBlocked = computed(() => isInspectionOrder.value && !canRecordInspection.value)

// ── Shared fields ────────────────────────────────────────────────────
const quantity = ref<number | null>(null)
const completionDate = ref<Date>(todayStart())
// A completion is reported for a day that has begun and not before the
// order was first started, as the backend checks, both on the tenant's
// calendar.
const latestCompletionDate = computed(() => todayStart())
const earliestCompletionDate = computed(() =>
  props.order?.actual_start ? toLocalDayStart(props.order.actual_start) : undefined,
)
const note = ref('')
const operatorId = ref<number | null>(null)
const { submitting, errorMessage, run } = useSubmitAction((e) => {
  const key = productionErrorKey(e)
  return key ? t(key) : null
})

const operatorRequired = computed(() => currentUserStore.isSharedAccount)

const operatorOptions = computed(() =>
  store.operators.map((op) => ({ label: op.full_name, value: op.id })),
)

// ── Inspection-only fields ───────────────────────────────────────────
const acceptedQty = ref<number | null>(null)
const rejectedQty = ref<number | null>(0)
// Why the rejected pieces failed, kept for the lot's inspection report.
const rejectReason = ref<ScrapReason | null>(null)
const rejectReasonOptions = computed(() =>
  SCRAP_REASONS.map((value) => ({ value, label: t(scrapReasonLabelKey(value)) })),
)
// One row per rejected piece, while rejectedQty is a whole number.
const perUnit = ref<LotOriginDisposition[]>([])
const reworkQty = ref<number | null>(0)
const scrapQty = ref<number | null>(0)

const dispositionOptions = computed(() => [
  { label: t('productionQueue.completion.rework'), value: 'rework' },
  { label: t('productionQueue.completion.replacement'), value: 'replacement' },
])

const isIntegerRejected = computed(
  () => rejectedQty.value !== null && Number.isInteger(rejectedQty.value),
)

// New rows default to rework; shrinking truncates.
watch(rejectedQty, (rej) => {
  if (rej === null || rej < 0 || !Number.isInteger(rej)) {
    perUnit.value = []
    return
  }
  const n = Math.round(rej)
  if (perUnit.value.length === n) return
  perUnit.value =
    perUnit.value.length < n
      ? [...perUnit.value, ...(Array(n - perUnit.value.length).fill('rework') as LotOriginDisposition[])]
      : perUnit.value.slice(0, n)
})

const reworkTotal = computed(() => {
  if (!rejectedQty.value) return 0
  if (isIntegerRejected.value) return perUnit.value.filter((d) => d === 'rework').length
  return reworkQty.value ?? 0
})

const scrapTotal = computed(() => {
  if (!rejectedQty.value) return 0
  if (isIntegerRejected.value) return perUnit.value.filter((d) => d === 'replacement').length
  return scrapQty.value ?? 0
})

// Only the fractional two-field fallback can mismatch.
const dispositionValid = computed(() => {
  if (!rejectedQty.value) return true
  if (isIntegerRejected.value) return true
  const sum = (reworkQty.value ?? 0) + (scrapQty.value ?? 0)
  return Math.abs(sum - rejectedQty.value) < 1e-6
})

const hasMeasurementFile = computed(() =>
  props.order
    ? filesStore
        .getFiles(props.order.id)
        .some((f) => f.category === 'measurement_report')
    : false,
)

watch(visible, (isVisible) => {
  if (!isVisible) return
  // What a completion may still book: the order's quantity less every piece
  // it processed, rejected and scrapped ones included.
  const remaining = props.order ? props.order.quantity_open : null
  quantity.value = remaining
  acceptedQty.value = remaining
  rejectedQty.value = 0
  rejectReason.value = null
  perUnit.value = []
  reworkQty.value = 0
  scrapQty.value = 0
  completionDate.value = todayStart()
  note.value = ''
  operatorId.value = null
  errorMessage.value = null
  if (props.order && requiresEvidence.value) {
    void filesStore.fetchFiles(props.order.id)
  }
})

const isValid = computed(() => {
  if (!completionDate.value) return false
  if (operatorRequired.value && operatorId.value === null) return false

  if (!isInspectionOrder.value) {
    return quantity.value !== null && quantity.value > 0
  }

  if (permissionBlocked.value) return false
  if (acceptedQty.value === null || acceptedQty.value < 0) return false
  if (rejectedQty.value === null || rejectedQty.value < 0) return false
  if (acceptedQty.value + rejectedQty.value <= 0) return false
  if (!dispositionValid.value) return false
  if (rejectedQty.value > 0 && rejectReason.value === null) return false
  if (requiresEvidence.value && !hasMeasurementFile.value) return false
  return true
})

async function onSubmit(): Promise<void> {
  const order = props.order
  if (!order) return
  if (!isValid.value) {
    errorMessage.value = t('productionQueue.completion.errors.invalid')
    return
  }

  const dateParam = dateToParam(completionDate.value)
  if (!dateParam) {
    errorMessage.value = t('productionQueue.completion.errors.invalid')
    return
  }

  await run(async () => {
    const updated = await store.recordCompletion(
      order.id,
      isInspectionOrder.value
        ? {
            quantity: acceptedQty.value! + rejectedQty.value!,
            quantity_accepted: acceptedQty.value!,
            quantity_rejected: rejectedQty.value!,
            quantity_rework: reworkTotal.value,
            quantity_scrap: scrapTotal.value,
            ...(rejectedQty.value! > 0 && rejectReason.value ? { reject_reason: rejectReason.value } : {}),
            completion_date: dateParam,
            note: note.value.trim() || undefined,
            ...(operatorId.value !== null ? { operator_id: operatorId.value } : {}),
          }
        : {
            quantity: quantity.value!,
            completion_date: dateParam,
            note: note.value.trim() || undefined,
            ...(operatorId.value !== null ? { operator_id: operatorId.value } : {}),
          },
    )
    visible.value = false
    emit('recorded', updated)

    if (updated.created_lots?.length) {
      const names = updated.created_lots
        .map((lot) =>
          lot.disposition === 'rework'
            ? t('productionQueue.completion.createdLotRework', { lotNumber: lot.lot_number })
            : t('productionQueue.completion.createdLotReplacement', { lotNumber: lot.lot_number }),
        )
        .join(', ')
      toast.success(t('productionQueue.completion.createdLotsToast', { lots: names }))
    }
  }, t('productionQueue.completion.errors.unknown'))
}

defineExpose({
  quantity,
  completionDate,
  operatorId,
  isValid,
  acceptedQty,
  rejectedQty,
  rejectReason,
  perUnit,
  reworkQty,
  scrapQty,
  reworkTotal,
  scrapTotal,
  dispositionValid,
  isInspectionOrder,
  requiresEvidence,
  permissionBlocked,
  hasMeasurementFile,
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: isInspectionOrder ? 'var(--dialog-width-md)' : 'var(--dialog-width-sm)' }"
  >
    <template #header>
      <div class="completion-header">
        <span class="p-dialog-title">{{ t('productionQueue.completion.title') }}</span>
        <Button
          type="button"
          class="completion-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('productionQueue.completion.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('productionQueue.completion.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <div v-if="order" class="completion-form">
      <Message v-if="permissionBlocked" severity="warn" :closable="false">
        {{ t('productionQueue.completion.permissionDenied') }}
      </Message>

      <template v-if="!isInspectionOrder">
        <div class="field">
          <label :for="`${uid}-quantity`">{{ t('productionQueue.completion.quantity') }} *</label>
          <InputNumber v-model="quantity" :input-id="`${uid}-quantity`" :min="1" :max-fraction-digits="0" fluid />
        </div>
      </template>

      <template v-else>
        <div class="field-row-pair">
          <div class="field">
            <label :for="`${uid}-accepted`">{{ t('productionQueue.completion.accepted') }} *</label>
            <InputNumber
              v-model="acceptedQty"
              :input-id="`${uid}-accepted`"
              :min="0"
              :max-fraction-digits="0"
              :disabled="permissionBlocked"
              fluid
            />
          </div>
          <div class="field">
            <label :for="`${uid}-rejected`">{{ t('productionQueue.completion.rejected') }} *</label>
            <InputNumber
              v-model="rejectedQty"
              :input-id="`${uid}-rejected`"
              :min="0"
              :max-fraction-digits="0"
              :disabled="permissionBlocked"
              fluid
            />
          </div>
        </div>

        <div v-if="!permissionBlocked && rejectedQty && rejectedQty > 0" class="field">
          <label :id="`${uid}-reject-reason-label`" :for="`${uid}-reject-reason`">
            {{ t('productionQueue.completion.rejectReason') }} *
          </label>
          <Select
            v-model="rejectReason"
            :input-id="`${uid}-reject-reason`"
            :aria-labelledby="`${uid}-reject-reason-label`"
            :options="rejectReasonOptions"
            option-label="label"
            option-value="value"
            :placeholder="t('productionQueue.completion.rejectReasonPlaceholder')"
            fluid
            data-testid="completion-reject-reason"
          />
        </div>

        <div
          v-if="!permissionBlocked && rejectedQty && rejectedQty > 0 && isIntegerRejected"
          class="field"
        >
          <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- captions every row below, each control names it through aria-labelledby -->
          <label :id="`${uid}-per-unit`">{{ t('productionQueue.completion.perUnitTitle') }}</label>
          <div class="per-unit-rows">
            <div v-for="(_, idx) in perUnit" :key="idx" class="per-unit-row">
              <span :id="`${uid}-per-unit-${idx}`" class="per-unit-label">{{
                t('productionQueue.completion.perUnitPiece', { n: idx + 1 })
              }}</span>
              <SelectButton
                v-model="perUnit[idx]"
                :aria-labelledby="`${uid}-per-unit ${uid}-per-unit-${idx}`"
                :options="dispositionOptions"
                option-label="label"
                option-value="value"
                :allow-empty="false"
              />
            </div>
          </div>
        </div>

        <div
          v-else-if="!permissionBlocked && rejectedQty && rejectedQty > 0"
          class="field-row-pair"
        >
          <div class="field">
            <label :for="`${uid}-rework-quantity`">{{ t('productionQueue.completion.reworkQuantity') }}</label>
            <InputNumber
              v-model="reworkQty"
              :input-id="`${uid}-rework-quantity`"
              :min="0"
              :max-fraction-digits="0"
              fluid
            />
          </div>
          <div class="field">
            <label :for="`${uid}-scrap-quantity`">{{ t('productionQueue.completion.scrapQuantity') }}</label>
            <InputNumber
              v-model="scrapQty"
              :input-id="`${uid}-scrap-quantity`"
              :min="0"
              :max-fraction-digits="0"
              fluid
            />
          </div>
        </div>

        <Message
          v-if="!permissionBlocked && rejectedQty && rejectedQty > 0 && dispositionValid"
          severity="info"
          :closable="false"
        >
          {{
            t('productionQueue.completion.dispositionSummary', {
              rework: reworkTotal,
              scrap: scrapTotal,
            })
          }}
        </Message>
        <Message
          v-if="!permissionBlocked && rejectedQty && rejectedQty > 0 && !dispositionValid"
          severity="error"
          :closable="false"
        >
          {{ t('productionQueue.completion.errors.dispositionSum') }}
        </Message>

        <div v-if="!permissionBlocked && requiresEvidence" class="field">
          <FilesSection
            :item-id="order.id"
            :files-store="filesStore"
            :multi="MEASUREMENT_FILES"
            :can-edit="true"
            title-key="productionQueue.completion.files.title"
            :fetch-blob="getProductionOrderFileBlob"
          />
          <Message v-if="!hasMeasurementFile" severity="warn" :closable="false">
            {{ t('productionQueue.completion.evidenceRequired') }}
          </Message>
        </div>
      </template>

      <div class="field">
        <label :for="`${uid}-date`">{{ t('productionQueue.completion.date') }} *</label>
        <DatePicker
          v-model="completionDate"
          :input-id="`${uid}-date`"
          show-button-bar
          :max-date="latestCompletionDate"
          :min-date="earliestCompletionDate"
          :disabled="permissionBlocked"
          fluid
        />
      </div>

      <div v-if="operatorRequired" class="field">
        <label :id="`${uid}-label-label`" :for="`${uid}-operators`"> {{ t('productionQueue.operators.label') }} * </label>
        <Select
          v-model="operatorId"
          :input-id="`${uid}-operators`"
          :aria-labelledby="`${uid}-label-label`"
          :options="operatorOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('productionQueue.operators.placeholderRequired')"
          :disabled="operatorOptions.length === 0 || permissionBlocked"
          fluid
        />
        <Message v-if="operatorOptions.length === 0" severity="warn" :closable="false">
          {{ t('productionQueue.operators.noneAssigned') }}
        </Message>
      </div>

      <div class="field">
        <label :for="`${uid}-note`">{{ t('productionQueue.completion.note') }}</label>
        <Textarea v-model="note" :id="`${uid}-note`" rows="2" auto-resize :disabled="permissionBlocked" fluid />
      </div>

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
        :label="t('productionQueue.completion.submit')"
        :loading="submitting"
        :disabled="!isValid"
        @click="onSubmit"
      />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="production/completions" />
</template>

<style scoped lang="scss">
.completion-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.completion-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.completion-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.field-row-pair {
  display: flex;
  gap: var(--space-3);

  .field {
    flex: 1;
  }
}

.per-unit-rows {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-height: 12rem;
  overflow-y: auto;
}

.per-unit-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.per-unit-label {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
