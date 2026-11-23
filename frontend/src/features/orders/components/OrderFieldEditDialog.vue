<script setup lang="ts">
import { computed, reactive, ref, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { dateToParam, toLocalDayStart } from '@/core/utils/dates'
import { useOrdersStore } from '../stores/ordersStore'
import { useSuppliersStore } from '@/features/suppliers'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import TextChipsInput from '@/shared/components/forms/TextChipsInput.vue'
import type { OrderResponse } from '../types/ordersResponse'
import type { OrderUpdateRequest } from '../types/ordersRequest'

export type OrderEditField =
  | 'supplier'
  | 'expected_delivery_date'
  | 'storage_place'
  | 'supplier_order_numbers'
  | 'note'

/**
 * For consumers that don't render off the orders list store, which
 * `ordersStore.update` refreshes and they never read.
 */
const emit = defineEmits<{ saved: [] }>()

const { t } = useI18n()
const ordersStore = useOrdersStore()
const suppliersStore = useSuppliersStore()

const visible = ref(false)
const order = ref<OrderResponse | null>(null)
const field = ref<OrderEditField | null>(null)
const { submitting, errorMessage: error, run } = useSubmitAction()

const form = reactive({
  supplier_id: null as number | null,
  note: '',
  expected_delivery_date: null as Date | null,
  storage_place: '',
  supplier_order_numbers: [] as string[],
  propagateDeliveryDate: true,
})

const numbersInput = useTemplateRef<{ commitPending(): void }>('numbersInput')

// Referencing an archived supplier is allowed; the picker keeps archived
// rows selectable and tagged (see useArchivableOptions.ts).
const { sortedOptions: supplierOptions, isArchived: isSupplierArchived } = useArchivableOptions(
  computed(() => suppliersStore.items),
)
const selectedSupplier = computed(() => suppliersStore.getById(form.supplier_id) ?? null)

const title = computed(() => {
  switch (field.value) {
    case 'supplier':
      return t('orders.edit.fields.supplier')
    case 'expected_delivery_date':
      return t('orders.edit.fields.expectedDelivery')
    case 'storage_place':
      return t('orders.edit.fields.storagePlace')
    case 'supplier_order_numbers':
      return t('orders.edit.fields.supplierOrderNumbers')
    case 'note':
      return t('orders.edit.fields.note')
    default:
      return ''
  }
})

function open(target: OrderResponse, editField: OrderEditField): void {
  order.value = target
  field.value = editField
  error.value = null
  form.supplier_id = target.supplier_id
  form.note = target.note ?? ''
  form.expected_delivery_date = target.expected_delivery_date
    ? toLocalDayStart(target.expected_delivery_date)
    : null
  form.storage_place = target.storage_place ?? ''
  form.supplier_order_numbers = [...target.supplier_order_numbers]
  form.propagateDeliveryDate = true
  if (editField === 'supplier' && suppliersStore.items.length === 0) void suppliersStore.refresh()
  visible.value = true
}

async function save(payload: Omit<OrderUpdateRequest, 'expected_edit_version'>): Promise<void> {
  const current = order.value
  if (!current) return
  await run(async () => {
    await ordersStore.update(current.id, {
      ...payload,
      expected_edit_version: current.edit_version,
    })
    visible.value = false
    emit('saved')
  }, t('orders.edit.errors.unknown'))
}

// The supplier order numbers have their own endpoint, since they stay
// editable with write:orders after the order went out.
async function saveSupplierOrderNumbers(): Promise<void> {
  const current = order.value
  if (!current) return
  numbersInput.value?.commitPending()
  await run(async () => {
    await ordersStore.setSupplierOrderNumbers(current.id, {
      numbers: form.supplier_order_numbers,
      expected_edit_version: current.edit_version,
    })
    visible.value = false
    emit('saved')
  }, t('orders.edit.errors.unknown'))
}

function onSave(): void {
  switch (field.value) {
    case 'supplier':
      void save({ supplier_id: form.supplier_id })
      break
    case 'expected_delivery_date':
      void save({
        expected_delivery_date: dateToParam(form.expected_delivery_date),
        update_items_delivery_date: form.propagateDeliveryDate,
      })
      break
    case 'storage_place':
      void save({ storage_place: form.storage_place.trim() || null })
      break
    case 'supplier_order_numbers':
      void saveSupplierOrderNumbers()
      break
    case 'note':
      void save({ note: form.note.trim() || null })
      break
  }
}

defineExpose({ open })
</script>

<template>
  <Dialog v-model:visible="visible" modal :header="title" :style="{ width: 'var(--dialog-width-sm)' }">
    <div class="field-editor" v-if="field === 'supplier'">
      <Select
        v-model="form.supplier_id"
        :aria-label="title"
        :options="supplierOptions"
        option-label="name"
        option-value="id"
        :loading="suppliersStore.loading"
        filter
        show-clear
        fluid
        autofocus
      >
        <template #option="{ option }">
          <span>{{ option.name }}</span>
          <ArchivedOptionTag v-if="option.archived" />
        </template>
        <template #value="{ value }">
          <span v-if="value">{{ selectedSupplier?.name }}</span>
          <ArchivedOptionTag v-if="selectedSupplier?.archived" />
        </template>
      </Select>
      <ArchivedSelectionWarning v-if="isSupplierArchived(selectedSupplier)" />
    </div>

    <div class="field-editor" v-else-if="field === 'expected_delivery_date'">
      <DatePicker v-model="form.expected_delivery_date" show-button-bar show-clear fluid autofocus />
      <div class="propagate-row">
        <Checkbox v-model="form.propagateDeliveryDate" input-id="dialog-propagate-date" binary />
        <label for="dialog-propagate-date" class="propagate-label">
          {{ t('orders.edit.fields.propagateDeliveryDate') }}
        </label>
      </div>
    </div>

    <div class="field-editor" v-else-if="field === 'storage_place'">
      <InputText v-model="form.storage_place" fluid autofocus @keyup.enter="onSave" />
    </div>

    <div class="field-editor" v-else-if="field === 'supplier_order_numbers'">
      <TextChipsInput
        ref="numbersInput"
        v-model="form.supplier_order_numbers"
        :aria-label="title"
        autofocus
      />
      <small class="field-hint">{{ t('orders.edit.supplierOrderNumbersHint') }}</small>
    </div>

    <div class="field-editor" v-else-if="field === 'note'">
      <Textarea v-model="form.note" :aria-label="title" rows="3" auto-resize fluid autofocus />
    </div>

    <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="submitting"
        @click="visible = false"
      />
      <Button :label="t('common.save')" :loading="submitting" @click="onSave" />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.field-editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.propagate-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-1);
}

.field-hint {
  color: var(--p-text-muted-color);
}

.propagate-label {
  font-size: var(--font-size-sm);
  cursor: pointer;
}
</style>
