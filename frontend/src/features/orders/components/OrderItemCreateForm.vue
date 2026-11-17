<script setup lang="ts">
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { dateToParam as formatDate } from '@/core/utils/dates'
import { currencyInputPrefix } from '@/core/utils/currency'
import { computed, reactive, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useOrdersStore } from '../stores/ordersStore'
import { useSuppliersStore } from '@/features/suppliers'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { BoughtItemSelect } from '@/features/bought-items'
import ProjectSelect from '@/shared/components/project/ProjectSelect.vue'

import type { OrderItemResponse } from '../types/ordersResponse'
import type { BoughtItemResponse } from '@/features/bought-items'
import type { ProjectRef } from '@/core/types/projectRef'
import { BOUGHT_ITEM_UNIT_CODES, DEFAULT_UNIT, quantityFractionDigits } from '@/shared/utils/units'

const props = withDefaults(
  defineProps<{
    orderId: number
    supplierId: number
    presetItem?: BoughtItemResponse | null
    initialVirtual?: boolean
  }>(),
  { initialVirtual: false },
)

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  created: [item: OrderItemResponse]
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()

const ordersStore = useOrdersStore()
const suppliersStore = useSuppliersStore()

interface FormState {
  isVirtual: boolean
  item: BoughtItemResponse | null
  virtualName: string
  supplier_id: number | null
  project: ProjectRef | null
  quantity: number | null
  unit: string
  items_per_unit: number
  price: number | null
  expected_delivery_date: Date | null
  note: string
}

function createEmptyForm(): FormState {
  return {
    isVirtual: props.initialVirtual,
    item: props.presetItem ?? null,
    virtualName: '',
    supplier_id: props.supplierId || null,
    project: null,
    quantity: null,
    unit: DEFAULT_UNIT,
    items_per_unit: 1,
    price: null,
    expected_delivery_date: null,
    note: '',
  }
}

const form = reactive(createEmptyForm())
const { submitting, errorMessage, run } = useSubmitAction()

// Referencing an already-archived supplier is allowed. The picker keeps
// archived rows selectable, sorted after live ones, each tagged (see
// useArchivableOptions.ts).
const { sortedOptions: supplierOptions, isArchived: isSupplierArchived } = useArchivableOptions(
  computed(() => suppliersStore.items),
)
const selectedSupplier = computed(
  () => suppliersStore.getById(form.supplier_id) ?? null,
)

const unitOptions = computed(() =>
  BOUGHT_ITEM_UNIT_CODES.map((code) => ({ value: code, label: t(`boughtItems.units.${code}`) })),
)

watch(
  visible,
  (isVisible) => {
    if (!isVisible) return
    const empty = createEmptyForm()
    Object.assign(form, { ...empty, supplier_id: props.supplierId || null })
    errorMessage.value = null
    if (suppliersStore.items.length === 0) {
      void suppliersStore.refresh()
    }
  },
  { immediate: true },
)

function isFormValid(): boolean {
  return (
    (form.isVirtual ? form.virtualName.trim().length > 0 : form.item !== null) &&
    form.supplier_id !== null &&
    form.project !== null &&
    form.quantity !== null &&
    form.quantity > 0 &&
    form.unit.trim().length > 0
  )
}

async function onSubmit(): Promise<void> {
  if (!isFormValid()) {
    errorMessage.value = t('orders.items.create.errors.required')
    return
  }

  await run(async () => {
    const created = await ordersStore.addItem(props.orderId, {
      ...(form.isVirtual
        ? { virtual_name: form.virtualName.trim() }
        : { bought_item_id: form.item!.id }),
      supplier_id: form.supplier_id!,
      project_id: form.project!.id,
      quantity: form.quantity!,
      unit: form.unit.trim(),
      items_per_unit: form.items_per_unit,
      price: form.price !== null ? Math.round(form.price * 100) : null,
      expected_delivery_date: formatDate(form.expected_delivery_date),
      note: form.note.trim() || null,
    })
    visible.value = false
    emit('created', created)
  }, t('orders.items.create.errors.unknown'))
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('orders.items.create.title')"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <form class="create-form" @submit.prevent="onSubmit">
      <div class="form-grid">
        <div class="field field-wide checkbox-field">
          <Checkbox v-model="form.isVirtual" input-id="order-item-virtual" :binary="true" />
          <label for="order-item-virtual">{{ t('orders.items.create.fields.isVirtual') }}</label>
        </div>

        <div class="field field-wide">
          <label :id="`${uid}-item-label`" :for="`${uid}-item`">{{ t('orders.items.create.fields.item') }} *</label>
          <BoughtItemSelect
            v-if="!form.isVirtual"
            v-model="form.item"
            :input-id="`${uid}-item`"
            :aria-labelledby="`${uid}-item-label`"
            :placeholder="t('orders.items.create.fields.itemPlaceholder')"
            fluid
          />
          <InputText
            v-else
            v-model="form.virtualName"
            :placeholder="t('orders.items.create.fields.virtualNamePlaceholder')"
            fluid
          />
        </div>

        <div class="field field-wide">
          <label :id="`${uid}-supplier-label`" :for="`${uid}-supplier`">
            {{ t('orders.items.create.fields.supplier') }} *
          </label>
          <Select
            v-model="form.supplier_id"
            :input-id="`${uid}-supplier`"
            :aria-labelledby="`${uid}-supplier-label`"
            :options="supplierOptions"
            option-label="name"
            option-value="id"
            :loading="suppliersStore.loading"
            :placeholder="t('orders.items.create.fields.supplierPlaceholder')"
            filter
            show-clear
            fluid
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

        <div class="field field-wide">
          <label :id="`${uid}-project-label`" :for="`${uid}-project`">{{ t('orders.items.create.fields.project') }} *</label>
          <ProjectSelect
            v-model="form.project"
            :input-id="`${uid}-project`"
            :aria-labelledby="`${uid}-project-label`"
            :placeholder="t('orders.items.create.fields.projectPlaceholder')"
            fluid
          />
        </div>

        <div class="field">
          <label :for="`${uid}-quantity`">{{ t('orders.items.create.fields.quantity') }} *</label>
          <InputNumber
            v-model="form.quantity"
            :input-id="`${uid}-quantity`"
            :min="quantityFractionDigits(form.unit) === 0 ? 1 : 0.001"
            :max-fraction-digits="quantityFractionDigits(form.unit)"
            fluid
          />
        </div>

        <div class="field">
          <label :id="`${uid}-unit-label`" :for="`${uid}-unit`">{{ t('orders.items.create.fields.unit') }} *</label>
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
          <label :for="`${uid}-items-per-unit`">{{ t('orders.items.create.fields.itemsPerUnit') }}</label>
          <InputNumber
            v-model="form.items_per_unit"
            :input-id="`${uid}-items-per-unit`"
            :min="0.001"
            :max-fraction-digits="3"
            fluid
          />
        </div>

        <div class="field">
          <label :for="`${uid}-price`">{{ t('orders.items.create.fields.price') }}</label>
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
          <label :for="`${uid}-expected-delivery`">{{ t('orders.items.create.fields.expectedDelivery') }}</label>
          <DatePicker
            v-model="form.expected_delivery_date"
            :input-id="`${uid}-expected-delivery`"
            show-button-bar
            show-clear
            fluid
          />
        </div>

        <div class="field field-wide">
          <label :for="`${uid}-note`">{{ t('orders.items.create.fields.note') }}</label>
          <Textarea v-model="form.note" :id="`${uid}-note`" rows="2" auto-resize fluid />
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
      <Button :label="t('common.save')" :loading="submitting" @click="onSubmit" />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.create-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.field-wide {
  grid-column: 1 / -1;
}

.checkbox-field {
  flex-direction: row;
  align-items: center;
  gap: var(--space-2);
}
</style>
