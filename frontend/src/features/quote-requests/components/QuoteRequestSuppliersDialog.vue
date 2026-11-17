<script setup lang="ts">
// Adds suppliers to ask for an offer. Those already on the request are left
// out of the list; an archived supplier may be added and is tagged.
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSuppliersStore } from '@/features/suppliers'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { addQuoteRequestSuppliers } from '../api/addQuoteRequestSuppliers'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

const emit = defineEmits<{ saved: [request: QuoteRequestResponse] }>()

const { t } = useI18n()
const suppliersStore = useSuppliersStore()
const { submitting, errorMessage, run } = useSubmitAction()

const visible = ref(false)
const request = ref<QuoteRequestResponse | null>(null)
const supplierIds = ref<number[]>([])

const present = computed(() => new Set(request.value?.suppliers.map((s) => s.supplier_id) ?? []))
const { sortedOptions, isArchived } = useArchivableOptions(
  computed(() => suppliersStore.items.filter((s) => !present.value.has(s.id))),
)
const selected = computed(() =>
  supplierIds.value.map((id) => suppliersStore.getById(id)).filter((s) => s !== undefined),
)

function open(target: QuoteRequestResponse): void {
  request.value = target
  supplierIds.value = []
  errorMessage.value = null
  if (suppliersStore.items.length === 0) void suppliersStore.refresh()
  visible.value = true
}

async function onSave(): Promise<void> {
  const target = request.value
  if (!target || supplierIds.value.length === 0) return
  await run(async () => {
    const saved = await addQuoteRequestSuppliers(target.id, supplierIds.value)
    visible.value = false
    emit('saved', saved)
  }, t('quoteRequests.suppliersDialog.errors.unknown'))
}

defineExpose({ open })
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('quoteRequests.suppliersDialog.title')"
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <label id="rfq-add-suppliers-label" class="form-label" for="rfq-add-suppliers">
      {{ t('quoteRequests.create.suppliers') }}
    </label>
    <MultiSelect
      v-model="supplierIds"
      input-id="rfq-add-suppliers"
      aria-labelledby="rfq-add-suppliers-label"
      :options="sortedOptions"
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
        <ArchivedOptionTag v-if="option.archived" />
      </template>
    </MultiSelect>
    <ArchivedSelectionWarning v-if="isArchived(selected)" />
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
        :label="t('quoteRequests.suppliersDialog.submit')"
        :loading="submitting"
        :disabled="supplierIds.length === 0"
        @click="onSave"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.form-label {
  display: block;
  margin-bottom: var(--space-1);
  font-size: var(--font-size-sm);
}

.footer-error {
  margin-right: auto;
}
</style>
