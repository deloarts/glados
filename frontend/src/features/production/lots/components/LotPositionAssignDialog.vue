<script setup lang="ts">
import { extractApiError } from '@/core/utils/errors'
import { dateToParam as formatDate } from '@/core/utils/dates'
import { currencyInputPrefix } from '@/core/utils/currency'
import { computed, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { OrderSelect } from '@/features/orders'
import { OrderCreateForm } from '@/features/orders'
import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'
import { useMachineCapability } from '../../composables/useMachineCapability'

import type { OrderResponse } from '@/features/orders'
import type { LotPositionResponse } from '../../types/productionLotsResponse'
import { BOUGHT_ITEM_UNIT_CODES, DEFAULT_UNIT } from '@/shared/utils/units'

const props = defineProps<{
  lotId: number
  position: LotPositionResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  assigned: []
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const detailStore = useProductionLotDetailStore()
const { positionHasExternalMethods, getPreferredSupplierId } = useMachineCapability()

const stage = ref<'pick' | 'form'>('pick')
const selectedOrder = ref<OrderResponse | null>(null)
const showCreateOrder = ref(false)

const showNoExternalMethodWarning = computed(() => !positionHasExternalMethods(props.position))
const presetSupplierId = computed(() => getPreferredSupplierId(props.position))

interface FormState {
  unit: string
  items_per_unit: number
  price: number | null
  expected_delivery_date: Date | null
}

function createEmptyForm(): FormState {
  return { unit: DEFAULT_UNIT, items_per_unit: 1, price: null, expected_delivery_date: null }
}

const form = reactive(createEmptyForm())
const submitting = ref(false)
const errorMessage = ref<string | null>(null)

const unitOptions = computed(() =>
  BOUGHT_ITEM_UNIT_CODES.map((code) => ({ value: code, label: t(`boughtItems.units.${code}`) })),
)

watch(visible, (isVisible) => {
  if (!isVisible) return
  stage.value = 'pick'
  selectedOrder.value = null
  Object.assign(form, createEmptyForm())
  errorMessage.value = null
})

function onContinue(): void {
  if (!selectedOrder.value) return
  stage.value = 'form'
}

function onOrderCreated(order: OrderResponse): void {
  selectedOrder.value = order
  showCreateOrder.value = false
  stage.value = 'form'
}

function isFormValid(): boolean {
  return form.unit.trim().length > 0
}

async function onSubmit(): Promise<void> {
  if (!props.position || !selectedOrder.value || !detailStore.lot || !isFormValid()) {
    errorMessage.value = t('production.lots.detail.assign.errors.required')
    return
  }

  submitting.value = true
  errorMessage.value = null

  try {
    await detailStore.assignPosition(props.lotId, props.position.id, {
      order_id: selectedOrder.value.id,
      unit: form.unit.trim(),
      items_per_unit: form.items_per_unit,
      price: form.price !== null ? Math.round(form.price * 100) : null,
      expected_delivery_date: formatDate(form.expected_delivery_date),
    })
    visible.value = false
    emit('assigned')
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('production.lots.detail.assign.errors.unknown')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('production.lots.detail.assign.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <div v-if="stage === 'pick'" class="picker">
      <Message v-if="showNoExternalMethodWarning" severity="warn" :closable="false">
        {{ t('production.lots.detail.assign.noExternalMethodWarning') }}
      </Message>

      <div class="field">
        <label :id="`${uid}-select-order-label`" :for="`${uid}-select-order`">
          {{ t('production.lots.detail.assign.selectOrder') }}
        </label>
        <OrderSelect
          v-model="selectedOrder"
          :input-id="`${uid}-select-order`"
          :aria-labelledby="`${uid}-select-order-label`"
          fluid
        />
      </div>

      <Divider align="center">
        <span class="divider-label">{{ t('common.or') }}</span>
      </Divider>

      <Button
        :label="t('production.lots.detail.assign.createOrder')"
        icon="mdi mdi-plus"
        severity="secondary"
        outlined
        fluid
        @click="showCreateOrder = true"
      />
    </div>

    <form v-else class="assign-form" @submit.prevent="onSubmit">
      <div class="form-grid">
        <div class="field">
          <label :id="`${uid}-unit-label`" :for="`${uid}-unit`">
            {{ t('production.lots.detail.assign.fields.unit') }} *
          </label>
          <Select
            v-model="form.unit"
            :input-id="`${uid}-unit`"
            :aria-labelledby="`${uid}-unit-label`"
            :options="unitOptions"
            option-label="label"
            option-value="value"
            fluid
          />
        </div>
        <div class="field">
          <label :for="`${uid}-items-per-unit`">{{ t('production.lots.detail.assign.fields.itemsPerUnit') }}</label>
          <InputNumber
            v-model="form.items_per_unit"
            :input-id="`${uid}-items-per-unit`"
            :min="0.001"
            :max-fraction-digits="3"
            fluid
          />
        </div>
        <div class="field">
          <label :for="`${uid}-price`">{{ t('production.lots.detail.assign.fields.price') }}</label>
          <InputNumber
            v-model="form.price"
            :input-id="`${uid}-price`"
            :min="0"
            :min-fraction-digits="2"
            :max-fraction-digits="2"
            :prefix="currencyInputPrefix()"
            fluid
          />
        </div>
        <div class="field">
          <label :for="`${uid}-expected-delivery`">
            {{ t('production.lots.detail.assign.fields.expectedDelivery') }}
          </label>
          <DatePicker
            v-model="form.expected_delivery_date"
            :input-id="`${uid}-expected-delivery`"
            show-button-bar
            show-clear
            fluid
          />
        </div>
      </div>

      <Message v-if="errorMessage" severity="error" :closable="false">
        {{ errorMessage }}
      </Message>
    </form>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="submitting"
        @click="visible = false"
      />
      <Button
        v-if="stage === 'pick'"
        :label="t('common.continue')"
        :disabled="!selectedOrder"
        @click="onContinue"
      />
      <Button v-else :label="t('common.save')" :loading="submitting" @click="onSubmit" />
    </template>
  </Dialog>

  <OrderCreateForm
    v-model:visible="showCreateOrder"
    :preset-supplier-id="presetSupplierId"
    @created="onOrderCreated"
  />
</template>

<style scoped lang="scss">
.picker,
.assign-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.divider-label {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
