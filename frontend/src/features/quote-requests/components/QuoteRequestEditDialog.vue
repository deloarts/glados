<script setup lang="ts">
// Edits the note and the due date of a quote request.
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { dateToParam, toLocalDayStart } from '@/core/utils/dates'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import FormField from '@/shared/components/forms/FormField.vue'
import { updateQuoteRequest } from '../api/updateQuoteRequest'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

const emit = defineEmits<{ saved: [request: QuoteRequestResponse] }>()

const { t } = useI18n()
const { submitting, errorMessage, run } = useSubmitAction()

const visible = ref(false)
const request = ref<QuoteRequestResponse | null>(null)
const deadline = ref<Date | null>(null)
const note = ref('')

function open(target: QuoteRequestResponse): void {
  request.value = target
  deadline.value = target.deadline ? toLocalDayStart(target.deadline) : null
  note.value = target.note ?? ''
  errorMessage.value = null
  visible.value = true
}

async function onSave(): Promise<void> {
  const target = request.value
  if (!target) return
  await run(async () => {
    const saved = await updateQuoteRequest(target.id, {
      deadline: dateToParam(deadline.value),
      note: note.value.trim() || null,
      expected_edit_version: target.edit_version,
    })
    visible.value = false
    emit('saved', saved)
  }, t('quoteRequests.edit.errors.unknown'))
}

defineExpose({ open })
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('quoteRequests.edit.title')"
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <div class="edit-form">
      <FormField :label="t('quoteRequests.create.deadline')" v-slot="{ inputId }">
        <DatePicker v-model="deadline" :input-id="inputId" show-button-bar show-clear fluid />
      </FormField>
      <FormField :label="t('quoteRequests.create.note')" v-slot="{ id }">
        <Textarea :id="id" v-model="note" rows="3" auto-resize fluid />
      </FormField>
    </div>
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
        icon="mdi mdi-content-save-outline"
        :label="t('common.save')"
        :loading="submitting"
        @click="onSave"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.edit-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.footer-error {
  margin-right: auto;
}
</style>
