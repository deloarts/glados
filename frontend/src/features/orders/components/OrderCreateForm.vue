<script setup lang="ts">
import { extractApiError } from '@/core/utils/errors'
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useOrdersStore } from '../stores/ordersStore'
import { useSuppliersStore } from '@/features/suppliers'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import FormField from '@/shared/components/forms/FormField.vue'

import type { OrderCreateRequest } from '../types/ordersRequest'
import type { OrderResponse } from '../types/ordersResponse'

const props = defineProps<{
  presetSupplierId?: number | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  created: [order: OrderResponse]
}>()

const { t } = useI18n()

const ordersStore = useOrdersStore()
const suppliersStore = useSuppliersStore()

interface FormState {
  supplier_id: number | null
  note: string
}

function createEmptyForm(): FormState {
  return { supplier_id: props.presetSupplierId ?? null, note: '' }
}

const form = reactive(createEmptyForm())
const submitting = ref(false)
const errorMessage = ref<string | null>(null)

// Referencing an already-archived supplier is allowed. The picker keeps
// archived rows selectable, sorted after live ones, each tagged (see
// useArchivableOptions.ts).
const { sortedOptions: supplierOptions, isArchived: isSupplierArchived } = useArchivableOptions(
  computed(() => suppliersStore.items),
)
const selectedSupplier = computed(
  () => suppliersStore.getById(form.supplier_id) ?? null,
)

watch(visible, (isVisible) => {
  if (!isVisible) return
  Object.assign(form, createEmptyForm())
  errorMessage.value = null
  if (suppliersStore.items.length === 0) {
    void suppliersStore.refresh()
  }
})

function isFormValid(): boolean {
  return form.supplier_id !== null && form.supplier_id > 0
}

async function onSubmit(): Promise<void> {
  if (!isFormValid()) {
    errorMessage.value = t('orders.create.errors.required')
    return
  }

  submitting.value = true
  errorMessage.value = null

  const payload: OrderCreateRequest = {
    supplier_id: form.supplier_id!,
    note: form.note.trim() || null,
  }

  try {
    const created = await ordersStore.create(payload)
    visible.value = false
    emit('created', created)
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('orders.create.errors.unknown')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('orders.create.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <form class="create-form" @submit.prevent="onSubmit">
      <div class="field">
        <FormField
          :label="t('orders.create.fields.supplier')"
          required
          v-slot="{ inputId, labelId, ariaRequired }"
        >
          <Select
            v-model="form.supplier_id"
            :input-id="inputId"
            :aria-labelledby="labelId"
            :options="supplierOptions"
            option-label="name"
            option-value="id"
            :loading="suppliersStore.loading"
            :placeholder="t('orders.create.fields.supplierPlaceholder')"
            filter
            show-clear
            fluid
            :pt="{ label: { 'aria-required': ariaRequired } }"
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
        </FormField>
      </div>

      <div class="field">
        <FormField :label="t('orders.create.fields.note')" v-slot="{ id }">
          <Textarea :id="id" v-model="form.note" rows="3" auto-resize fluid />
        </FormField>
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
</style>
