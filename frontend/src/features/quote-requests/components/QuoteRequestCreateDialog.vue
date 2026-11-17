<script setup lang="ts">
// Starts a quote request with the suppliers to ask, a due date for the
// offers and a note. Lines come from the Manage Quotes panel or are passed
// in. An archived supplier may be picked; the picker tags it.
import { computed, reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { dateToParam } from '@/core/utils/dates'
import { useSuppliersStore } from '@/features/suppliers'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import FormField from '@/shared/components/forms/FormField.vue'
import { createQuoteRequest } from '../api/createQuoteRequest'
import type { QuoteRequestLineRequest } from '../types/quoteRequestsRequest'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

const props = withDefaults(
  defineProps<{
    /** Lines the request starts with, such as the panel's rows. */
    lines?: QuoteRequestLineRequest[]
    /** Suppliers suggested first, such as those ordered from before. */
    suggestedSupplierIds?: number[]
  }>(),
  { lines: () => [], suggestedSupplierIds: () => [] },
)

const visible = defineModel<boolean>('visible', { default: false })
const emit = defineEmits<{ created: [request: QuoteRequestResponse] }>()

const { t } = useI18n()
const suppliersStore = useSuppliersStore()
const { submitting, errorMessage, run } = useSubmitAction()

const form = reactive({
  supplierIds: [] as number[],
  deadline: null as Date | null,
  note: '',
})

const { sortedOptions, isArchived } = useArchivableOptions(computed(() => suppliersStore.items))
const supplierOptions = computed(() => {
  const suggested = new Set(props.suggestedSupplierIds)
  return [...sortedOptions.value].sort(
    (a, b) => Number(suggested.has(b.id)) - Number(suggested.has(a.id)),
  )
})
const selectedSuppliers = computed(() =>
  form.supplierIds.map((id) => suppliersStore.getById(id)).filter((s) => s !== undefined),
)

watch(visible, (open) => {
  if (!open) return
  form.supplierIds = []
  form.deadline = null
  form.note = ''
  errorMessage.value = null
  if (suppliersStore.items.length === 0) void suppliersStore.refresh()
})

async function onSubmit(): Promise<void> {
  await run(async () => {
    const created = await createQuoteRequest({
      supplier_ids: form.supplierIds,
      deadline: dateToParam(form.deadline),
      note: form.note.trim() || null,
      lines: props.lines,
    })
    visible.value = false
    emit('created', created)
  }, t('quoteRequests.create.errors.unknown'))
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('quoteRequests.create.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <form class="create-form" @submit.prevent="onSubmit">
      <FormField :label="t('quoteRequests.create.suppliers')" v-slot="{ inputId, labelId }">
        <MultiSelect
          v-model="form.supplierIds"
          :input-id="inputId"
          :aria-labelledby="labelId"
          :options="supplierOptions"
          option-label="name"
          option-value="id"
          :loading="suppliersStore.loading"
          :placeholder="t('quoteRequests.create.suppliersPlaceholder')"
          filter
          display="chip"
          fluid
        >
          <template #option="{ option }">
            <span>{{ option.name }}</span>
            <Tag
              v-if="props.suggestedSupplierIds.includes(option.id)"
              :value="t('quoteRequests.create.suggested')"
              severity="secondary"
              class="option-tag"
            />
            <ArchivedOptionTag v-if="option.archived" />
          </template>
        </MultiSelect>
        <ArchivedSelectionWarning v-if="isArchived(selectedSuppliers)" />
        <small class="hint">{{ t('quoteRequests.create.suppliersHint') }}</small>
      </FormField>

      <FormField :label="t('quoteRequests.create.deadline')" v-slot="{ inputId }">
        <DatePicker v-model="form.deadline" :input-id="inputId" show-button-bar show-clear fluid />
      </FormField>

      <FormField :label="t('quoteRequests.create.note')" v-slot="{ id }">
        <Textarea :id="id" v-model="form.note" rows="3" auto-resize fluid />
      </FormField>
    </form>

    <template #footer>
      <Message v-if="errorMessage" severity="error" :closable="false" class="footer-error">
        {{ errorMessage }}
      </Message>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        text
        :disabled="submitting"
        @click="visible = false"
      />
      <Button
        icon="mdi mdi-plus"
        :label="t('quoteRequests.create.submit')"
        :loading="submitting"
        @click="onSubmit"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.create-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.option-tag {
  margin-left: var(--space-2);
}

.footer-error {
  margin-right: auto;
}
</style>
