<script setup lang="ts">
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { useAppToast } from '@/core/composables/useAppToast'
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { SCRAP_REASONS, scrapReasonLabelKey } from '@/shared/utils/scrapReasons'
import type { ScrapReason } from '@/shared/utils/scrapReasons'

import { getOrder } from '../api/getOrder'
import { isDeliverableLine } from '../composables/useOrderItemActions'
import { useOrdersStore } from '../stores/ordersStore'
import type { OrderItemRejectionRequest } from '../types/ordersRequest'
import type { OrderItemResponse, RejectionOutcome } from '../types/ordersResponse'
import { formatUnit } from '@/shared/utils/units'

const props = defineProps<{
  visible: boolean
  orderId: number | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const ordersStore = useOrdersStore()
const toast = useAppToast()

const storagePlace = ref('')
// The shipment's delivery note, recorded on every line it books.
const deliveryNote = ref('')
// Whether damage was noted on that delivery note at handover.
const damageNoted = ref(false)
const { submitting: delivering, errorMessage: error, run } = useSubmitAction()

const loadingItems = ref(false)
const items = ref<OrderItemResponse[]>([])

interface LineRejectState {
  show: boolean
  quantity: number | null
  reason: ScrapReason | null
  note: string
  outcome: RejectionOutcome | null
  createReplacement: boolean
}

function defaultLineState(): LineRejectState {
  return { show: false, quantity: null, reason: null, note: '', outcome: null, createReplacement: true }
}

// One reject-block state per order item id, created lazily.
const lineStates = ref<Record<number, LineRejectState>>({})

function lineState(itemId: number): LineRejectState {
  const existing = lineStates.value[itemId]
  if (existing) return existing
  const created = defaultLineState()
  lineStates.value[itemId] = created
  return created
}

// A "deliver all" call only touches lines that can take a delivery, the
// lines whose actions offer it, so a canceled order lists none.
const eligibleItems = computed(() => items.value.filter((i) => isDeliverableLine(i)))

function remainingOf(item: OrderItemResponse): number {
  return item.quantity - item.quantity_delivered - (item.quantity_rejected_lost ?? 0)
}

function isMadeLine(item: OrderItemResponse): boolean {
  return item.line_type === 'MADE'
}

const reasonOptions = computed(() =>
  SCRAP_REASONS.map((r) => ({ label: t(scrapReasonLabelKey(r)), value: r })),
)

function lineValid(item: OrderItemResponse): boolean {
  const state = lineStates.value[item.id]
  if (!state || !state.quantity || state.quantity <= 0) return true
  if (state.quantity > remainingOf(item)) return false
  return !!state.reason && !!state.outcome
}

const canSubmit = computed(() => !delivering.value && eligibleItems.value.every(lineValid))

watch(
  () => props.visible,
  (val) => {
    if (val) {
      storagePlace.value = ''
      deliveryNote.value = ''
      damageNoted.value = false
      error.value = null
      lineStates.value = {}
      void loadItems()
    }
  },
)

async function loadItems(): Promise<void> {
  if (!props.orderId) return
  loadingItems.value = true
  try {
    const order = await getOrder(props.orderId)
    items.value = order.items ?? []
  } catch {
    // The plain "deliver all" action still works without the per-line list;
    // only the rejection UI is unavailable until the dialog is reopened.
    items.value = []
  } finally {
    loadingItems.value = false
  }
}

async function confirm(): Promise<void> {
  const orderId = props.orderId
  if (!orderId) return
  await run(async () => {
    const rejections: OrderItemRejectionRequest[] = eligibleItems.value.flatMap((item) => {
      const state = lineStates.value[item.id]
      if (!state || !state.quantity || state.quantity <= 0) return []
      return [
        {
          order_item_id: item.id,
          quantity_rejected: state.quantity,
          rejection_reason: state.reason!,
          rejection_note: state.note.trim() || undefined,
          rejection_outcome: state.outcome!,
          create_replacement:
            state.outcome === 'lost' && isMadeLine(item) ? state.createReplacement : true,
        },
      ]
    })

    const skipped = await ordersStore.deliverAllItems(
      orderId,
      storagePlace.value.trim() || undefined,
      rejections.length ? rejections : undefined,
      deliveryNote.value.trim() || undefined,
      // Passed only when ticked, so a booking without it calls as before.
      ...(damageNoted.value ? ([true] as const) : ([] as const)),
    )
    if (skipped > 0) {
      toast.info(
        t('orders.items.deliverAllDialog.title'),
        t('orders.items.deliverAllDialog.skipped', { count: skipped }),
      )
    }
    emit('update:visible', false)
  }, t('boughtItems.demands.detail.errors.unknown'))
}

defineExpose({
  storagePlace,
  loadingItems,
  items,
  eligibleItems,
  lineState,
  isMadeLine,
  canSubmit,
})
</script>

<template>
  <Dialog
    :visible="visible"
    @update:visible="emit('update:visible', $event)"
    modal
    :header="t('orders.items.deliverAllDialog.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <div class="deliver-form">
      <p class="deliver-all-info">{{ t('orders.items.deliverAllDialog.body') }}</p>
      <div class="field">
        <label :for="`${uid}-storage-place`">{{ t('orders.items.deliverDialog.storagePlace') }}</label>
        <InputText
          v-model="storagePlace"
          :id="`${uid}-storage-place`"
          :placeholder="t('orders.items.deliverDialog.storagePlaceholder')"
          fluid
        />
      </div>
      <div class="field">
        <label :for="`${uid}-delivery-note`">{{ t('orders.items.deliverAllDialog.deliveryNote') }}</label>
        <InputText v-model="deliveryNote" :id="`${uid}-delivery-note`" maxlength="100" fluid />
      </div>
      <label class="checkbox-toggle">
        <Checkbox v-model="damageNoted" binary data-testid="deliver-all-damage-noted" />
        <span>{{ t('orders.items.deliverAllDialog.damageNoted') }}</span>
      </label>

      <div v-if="loadingItems" class="loading-items">
        <ProgressSpinner style="width: 2rem; height: 2rem" stroke-width="4" />
      </div>
      <div v-else-if="eligibleItems.length" class="reject-lines">
        <div v-for="item in eligibleItems" :key="item.id" class="reject-line">
          <div
            class="reject-toggle"
            role="button"
            tabindex="0"
            @click="lineState(item.id).show = !lineState(item.id).show"
            @keydown.enter="lineState(item.id).show = !lineState(item.id).show"
            @keydown.space.prevent="lineState(item.id).show = !lineState(item.id).show"
          >
            <i
              class="mdi"
              :class="lineState(item.id).show ? 'mdi-chevron-up' : 'mdi-chevron-down'"
              aria-hidden="true"
            />
            <span class="reject-line-title">{{ item.item_article_name }}</span>
            <span class="reject-line-remaining"
              >{{ remainingOf(item) }} {{ formatUnit(item.unit) }}</span
            >
            <span class="reject-line-label">{{ t('orders.delivery.reject.toggle') }}</span>
          </div>

          <div v-if="lineState(item.id).show" class="reject-block">
            <div class="field">
              <label :for="`${uid}-quantity-${item.id}`">{{ t('orders.delivery.reject.quantity') }}</label>
              <InputNumber
                v-model="lineState(item.id).quantity"
                :input-id="`${uid}-quantity-${item.id}`"
                :min="0"
                :max="remainingOf(item)"
                :max-fraction-digits="3"
                fluid
              />
            </div>
            <div class="field">
              <label :id="`${uid}-reason-label-${item.id}`" :for="`${uid}-reason-${item.id}`">
                {{ t('orders.delivery.reject.reason') }} *
              </label>
              <Select
                v-model="lineState(item.id).reason"
                :input-id="`${uid}-reason-${item.id}`"
                :aria-labelledby="`${uid}-reason-label-${item.id}`"
                :options="reasonOptions"
                option-label="label"
                option-value="value"
                :placeholder="t('orders.delivery.reject.reasonPlaceholder')"
                fluid
              />
            </div>
            <div class="field">
              <label :for="`${uid}-note-${item.id}`">{{ t('orders.delivery.reject.note') }}</label>
              <Textarea v-model="lineState(item.id).note" :id="`${uid}-note-${item.id}`" rows="2" auto-resize fluid />
            </div>
            <div class="field">
              <label :for="`reject-outcome-redeliver-${item.id}`">{{ t('orders.delivery.reject.outcome') }} *</label>
              <div class="outcome-options">
                <div class="outcome-option">
                  <RadioButton
                    v-model="lineState(item.id).outcome"
                    :input-id="`reject-outcome-redeliver-${item.id}`"
                    value="redeliver"
                    :name="`reject-outcome-${item.id}`"
                  />
                  <label :for="`reject-outcome-redeliver-${item.id}`">{{
                    t('orders.delivery.reject.outcomeOptions.redeliver')
                  }}</label>
                </div>
                <div class="outcome-option">
                  <RadioButton
                    v-model="lineState(item.id).outcome"
                    :input-id="`reject-outcome-lost-${item.id}`"
                    value="lost"
                    :name="`reject-outcome-${item.id}`"
                  />
                  <label :for="`reject-outcome-lost-${item.id}`">{{
                    t('orders.delivery.reject.outcomeOptions.lost')
                  }}</label>
                </div>
              </div>
            </div>
            <label
              v-if="lineState(item.id).outcome === 'lost' && isMadeLine(item)"
              class="checkbox-toggle"
            >
              <Checkbox v-model="lineState(item.id).createReplacement" binary />
              <span>{{ t('orders.delivery.reject.createReplacement') }}</span>
            </label>
            <Message
              v-if="lineState(item.id).outcome === 'lost' && !(isMadeLine(item) && lineState(item.id).createReplacement)"
              severity="info"
              size="small"
              :closable="false"
            >
              {{ t('orders.delivery.reject.lostHint') }}
            </Message>
            <Message
              v-if="(lineState(item.id).quantity ?? 0) > remainingOf(item)"
              severity="error"
              :closable="false"
            >
              {{ t('orders.delivery.reject.errors.exceedsRemaining') }}
            </Message>
          </div>
        </div>
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
        :label="t('orders.actions.deliverAll')"
        icon="mdi mdi-check-all"
        :loading="delivering"
        :disabled="!canSubmit"
        severity="success"
        @click="confirm"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.deliver-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.deliver-all-info {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.loading-items {
  display: flex;
  justify-content: center;
  padding: var(--space-4) 0;
}

.reject-lines {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-height: 20rem;
  overflow-y: auto;
}

.reject-line {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--p-content-border-color);

  &:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }
}

.reject-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  font-size: var(--font-size-sm);
}

.reject-line-title {
  font-weight: 500;
  flex: 1;
}

.reject-line-remaining {
  color: var(--p-text-muted-color);
}

.reject-line-label {
  color: var(--p-primary-color);
  font-weight: 500;
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
