<script setup lang="ts">
import { extractApiError } from '@/core/utils/errors'
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { HelpDrawer } from '@/shared/help'

import { SCRAP_REASONS, scrapReasonLabelKey } from '@/shared/utils/scrapReasons'
import { quantityFractionDigits } from '@/shared/utils/units'
import type { ScrapReason } from '@/shared/utils/scrapReasons'

import { useOrdersStore } from '../stores/ordersStore'
import type { DeliveryRejectionRequest } from '../types/ordersRequest'
import type { OrderItemResponse, RejectionOutcome } from '../types/ordersResponse'

const props = defineProps<{
  visible: boolean
  orderId: number
  item: OrderItemResponse | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const ordersStore = useOrdersStore()

const storagePlace = ref('')
const quantity = ref<number | null>(null)
const delivering = ref(false)
const error = ref<string | null>(null)

const showReject = ref(false)
const rejectedQuantity = ref<number | null>(null)
const rejectReason = ref<ScrapReason | null>(null)
const rejectNote = ref('')
const rejectOutcome = ref<RejectionOutcome | null>(null)
const createReplacement = ref(true)

// Where the material comes from, for its genealogy into the lot that uses it.
const showMaterial = ref(false)
const supplierBatch = ref('')
const deliveryNote = ref('')
const certificate = ref('')
// Whether the receiver noted damage on the carrier's delivery note at
// handover, which a transport damage claim depends on.
const damageNoted = ref(false)

// Lost rejections reduce the remaining quantity like accepted deliveries,
// as in the backend's formula.
const remaining = computed(() =>
  props.item
    ? props.item.quantity - props.item.quantity_delivered - (props.item.quantity_rejected_lost ?? 0)
    : 0,
)

const isMadeLine = computed(() => props.item?.line_type === 'MADE')
// A MADE line always carries whole pieces of its lot.
const fractionDigits = computed(() =>
  isMadeLine.value ? 0 : quantityFractionDigits(props.item?.unit),
)
const showCreateReplacement = computed(() => rejectOutcome.value === 'lost' && isMadeLine.value)

// The delivered quantity that fills the line shrinks by whatever is set aside
// as rejected, since both draw from the same remaining line quantity.
const maxDeliverable = computed(() => Math.max(0, remaining.value - (rejectedQuantity.value ?? 0)))

// A MADE line carries exactly its lot's pieces. Any other line may take more
// within its over-delivery tolerance, which the backend checks, so its input
// has no cap and the dialog says when the delivery goes beyond the line.
const quantityCap = computed(() => (isMadeLine.value ? maxDeliverable.value : undefined))
const overDelivered = computed(() =>
  isMadeLine.value ? 0 : Math.max(0, (quantity.value ?? 0) - maxDeliverable.value),
)

watch(maxDeliverable, (max) => {
  if (quantity.value !== null && quantity.value > max) {
    quantity.value = max > 0 ? max : null
  }
})

const reasonOptions = computed(() =>
  SCRAP_REASONS.map((r) => ({ label: t(scrapReasonLabelKey(r)), value: r })),
)

const rejectValid = computed(() => {
  if (!rejectedQuantity.value || rejectedQuantity.value <= 0) return true
  if (rejectedQuantity.value > remaining.value) return false
  return !!rejectReason.value && !!rejectOutcome.value
})

const canSubmit = computed(
  () => !!quantity.value && quantity.value > 0 && rejectValid.value && !delivering.value,
)

watch(
  () => props.visible,
  (val) => {
    if (val) {
      storagePlace.value = ''
      quantity.value = remaining.value
      error.value = null
      showReject.value = false
      rejectedQuantity.value = null
      rejectReason.value = null
      rejectNote.value = ''
      rejectOutcome.value = null
      createReplacement.value = true
      showMaterial.value = false
      supplierBatch.value = ''
      deliveryNote.value = ''
      certificate.value = ''
      damageNoted.value = false
    }
  },
)

async function confirm(): Promise<void> {
  if (!props.item || !quantity.value || !rejectValid.value) return
  delivering.value = true
  error.value = null
  try {
    const rejection: DeliveryRejectionRequest | undefined =
      rejectedQuantity.value && rejectedQuantity.value > 0
        ? {
            quantity_rejected: rejectedQuantity.value,
            rejection_reason: rejectReason.value!,
            rejection_note: rejectNote.value.trim() || undefined,
            rejection_outcome: rejectOutcome.value!,
            create_replacement: showCreateReplacement.value ? createReplacement.value : true,
          }
        : undefined
    const material = {
      supplier_batch: supplierBatch.value.trim() || undefined,
      delivery_note_number: deliveryNote.value.trim() || undefined,
      certificate_reference: certificate.value.trim() || undefined,
      damage_noted_on_delivery_note: damageNoted.value || undefined,
    }
    const hasMaterial = Object.values(material).some((value) => value !== undefined)

    await ordersStore.deliverItem(
      props.orderId,
      props.item.id,
      quantity.value,
      storagePlace.value.trim() || undefined,
      rejection || hasMaterial
        ? { quantity_rejected: 0, create_replacement: true, ...rejection, ...material }
        : undefined,
    )
    emit('update:visible', false)
  } catch (e) {
    error.value = extractApiError(e) ?? t('boughtItems.demands.detail.errors.unknown')
  } finally {
    delivering.value = false
  }
}

defineExpose({
  quantity,
  showReject,
  rejectedQuantity,
  rejectReason,
  rejectNote,
  rejectOutcome,
  createReplacement,
  remaining,
  maxDeliverable,
  quantityCap,
  overDelivered,
  isMadeLine,
  showCreateReplacement,
  canSubmit,
  damageNoted,
})

const explainVisible = ref(false)
</script>

<template>
  <Dialog
    :visible="visible"
    @update:visible="emit('update:visible', $event)"
    modal
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <template #header>
      <div class="deliver-header">
        <span class="p-dialog-title">{{ t('orders.items.deliverDialog.title') }}</span>
        <Button
          type="button"
          class="deliver-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('orders.items.deliverDialog.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('orders.items.deliverDialog.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <div class="deliver-form">
      <div class="field">
        <label :for="`${uid}-quantity`">{{ t('orders.items.deliverDialog.quantity') }}</label>
        <InputNumber
          v-model="quantity"
          :input-id="`${uid}-quantity`"
          :min="fractionDigits === 0 ? 1 : 0.001"
          :max="quantityCap"
          :max-fraction-digits="fractionDigits"
          fluid
        />
        <small>{{ t('orders.items.deliverDialog.remaining', { remaining }) }}</small>
      </div>
      <Message v-if="overDelivered > 0" severity="info" :closable="false">
        {{ t('orders.items.deliverDialog.overDelivery', { extra: overDelivered }) }}
      </Message>
      <div class="field">
        <label :for="`${uid}-storage-place`">{{ t('orders.items.deliverDialog.storagePlace') }}</label>
        <InputText
          v-model="storagePlace"
          :id="`${uid}-storage-place`"
          :placeholder="t('orders.items.deliverDialog.storagePlaceholder')"
          fluid
        />
      </div>
      <label class="checkbox-toggle">
        <Checkbox v-model="damageNoted" binary data-testid="deliver-damage-noted" />
        <span>{{ t('orders.items.deliverDialog.damageNoted') }}</span>
      </label>

      <div
        class="reject-toggle"
        role="button"
        tabindex="0"
        @click="showMaterial = !showMaterial"
        @keydown.enter="showMaterial = !showMaterial"
        @keydown.space.prevent="showMaterial = !showMaterial"
      >
        <i
          class="mdi"
          :class="showMaterial ? 'mdi-chevron-up' : 'mdi-chevron-down'"
          aria-hidden="true"
        />
        <span>{{ t('orders.items.deliverDialog.material.toggle') }}</span>
      </div>

      <div v-if="showMaterial" class="reject-block">
        <div class="field">
          <label :for="`${uid}-batch`">{{ t('orders.items.deliverDialog.material.batch') }}</label>
          <InputText v-model="supplierBatch" :id="`${uid}-batch`" maxlength="100" fluid />
        </div>
        <div class="field">
          <label :for="`${uid}-delivery-note`">{{ t('orders.items.deliverDialog.material.deliveryNote') }}</label>
          <InputText v-model="deliveryNote" :id="`${uid}-delivery-note`" maxlength="100" fluid />
        </div>
        <div class="field">
          <label :for="`${uid}-certificate`">{{ t('orders.items.deliverDialog.material.certificate') }}</label>
          <InputText v-model="certificate" :id="`${uid}-certificate`" maxlength="100" fluid />
        </div>
      </div>

      <div
        class="reject-toggle"
        role="button"
        tabindex="0"
        @click="showReject = !showReject"
        @keydown.enter="showReject = !showReject"
        @keydown.space.prevent="showReject = !showReject"
      >
        <i class="mdi" :class="showReject ? 'mdi-chevron-up' : 'mdi-chevron-down'" aria-hidden="true" />
        <span>{{ t('orders.delivery.reject.toggle') }}</span>
      </div>

      <div v-if="showReject" class="reject-block">
        <div class="field">
          <label :for="`${uid}-quantity-2`">{{ t('orders.delivery.reject.quantity') }}</label>
          <InputNumber
            v-model="rejectedQuantity"
            :input-id="`${uid}-quantity-2`"
            :min="0"
            :max="remaining"
            :max-fraction-digits="fractionDigits"
            fluid
          />
        </div>
        <div class="field">
          <label :id="`${uid}-reason-label`" :for="`${uid}-reason`">{{ t('orders.delivery.reject.reason') }} *</label>
          <Select
            v-model="rejectReason"
            :input-id="`${uid}-reason`"
            :aria-labelledby="`${uid}-reason-label`"
            :options="reasonOptions"
            option-label="label"
            option-value="value"
            :placeholder="t('orders.delivery.reject.reasonPlaceholder')"
            fluid
          />
        </div>
        <div class="field">
          <label :for="`${uid}-note`">{{ t('orders.delivery.reject.note') }}</label>
          <Textarea v-model="rejectNote" :id="`${uid}-note`" rows="2" auto-resize fluid />
        </div>
        <div class="field">
          <label for="reject-outcome-redeliver">{{ t('orders.delivery.reject.outcome') }} *</label>
          <div class="outcome-options">
            <div class="outcome-option">
              <RadioButton
                v-model="rejectOutcome"
                input-id="reject-outcome-redeliver"
                value="redeliver"
                name="reject-outcome"
              />
              <label for="reject-outcome-redeliver">{{
                t('orders.delivery.reject.outcomeOptions.redeliver')
              }}</label>
            </div>
            <div class="outcome-option">
              <RadioButton
                v-model="rejectOutcome"
                input-id="reject-outcome-lost"
                value="lost"
                name="reject-outcome"
              />
              <label for="reject-outcome-lost">{{
                t('orders.delivery.reject.outcomeOptions.lost')
              }}</label>
            </div>
          </div>
        </div>
        <label v-if="showCreateReplacement" class="checkbox-toggle">
          <Checkbox v-model="createReplacement" binary />
          <span>{{ t('orders.delivery.reject.createReplacement') }}</span>
        </label>
        <Message
          v-if="rejectOutcome === 'lost' && !(showCreateReplacement && createReplacement)"
          severity="info"
          size="small"
          :closable="false"
        >
          {{ t('orders.delivery.reject.lostHint') }}
        </Message>
        <Message
          v-if="rejectedQuantity && rejectedQuantity > remaining"
          severity="error"
          :closable="false"
        >
          {{ t('orders.delivery.reject.errors.exceedsRemaining') }}
        </Message>
      </div>

      <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
    </div>
    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="delivering"
        @click="emit('update:visible', false)"
      />
      <Button
        :label="t('orders.actions.deliver')"
        icon="mdi mdi-check"
        :loading="delivering"
        :disabled="!canSubmit"
        severity="success"
        @click="confirm"
      />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="procurement/order-item-delivery" />
</template>

<style scoped lang="scss">
.deliver-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.deliver-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.deliver-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.reject-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  cursor: pointer;
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--p-primary-color);
  width: fit-content;
}

.reject-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.outcome-options {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.outcome-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.checkbox-toggle {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}
</style>
