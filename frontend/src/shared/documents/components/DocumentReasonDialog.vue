<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

/**
 * Asks for the reason of a document control step, such as why a new
 * revision starts or why a released revision is invalid; the reason is
 * kept with the document.
 */

defineProps<{
  header: string
  intro: string
  submitLabel: string
  submitIcon: string
  severity?: 'danger'
  busy?: boolean
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{ submit: [reason: string] }>()

const MAX_REASON_LENGTH = 2000

const { t } = useI18n()

const reason = ref('')
const submitted = ref(false)

watch(visible, (open) => {
  if (open) {
    reason.value = ''
    submitted.value = false
  }
})

const missing = computed(() => reason.value.trim() === '')

function submit(): void {
  submitted.value = true
  if (missing.value) return
  emit('submit', reason.value.trim())
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :header="header" :style="{ width: 'var(--dialog-width-md)' }" :breakpoints="{ '640px': '95vw' }">
    <form class="reason-form" @submit.prevent="submit">
      <p class="intro">{{ intro }}</p>
      <label for="document-reason">{{ t('documents.reason.label') }}</label>
      <Textarea
        id="document-reason"
        v-model="reason"
        :maxlength="MAX_REASON_LENGTH"
        :invalid="submitted && missing"
        rows="3"
        auto-resize
        fluid
        data-testid="document-reason"
      />
      <small v-if="submitted && missing" class="error">{{ t('documents.reason.required') }}</small>
    </form>
    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
      <Button
        :label="submitLabel"
        :icon="submitIcon"
        :severity="severity"
        :loading="busy"
        data-testid="document-reason-submit"
        @click="submit"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.reason-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.intro {
  margin: 0 0 var(--space-2);
  color: var(--p-text-muted-color);
}

.error {
  color: var(--p-red-500);
}
</style>
