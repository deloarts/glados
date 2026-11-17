<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { MAX_TEXT_LENGTH } from '../utils/state'

/** Asks why a new revision is started; the reason is kept with the revision. */

defineProps<{
  revision: string
  busy?: boolean
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{ revise: [reason: string] }>()

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
  emit('revise', reason.value.trim())
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('checklists.revise.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
    :breakpoints="{ '640px': '95vw' }"
  >
    <form class="revise-form" @submit.prevent="submit">
      <p class="intro">{{ t('checklists.revise.intro', { revision }) }}</p>
      <label for="cl-revise-reason">{{ t('checklists.revise.reason') }}</label>
      <Textarea
        id="cl-revise-reason"
        v-model="reason"
        :maxlength="MAX_TEXT_LENGTH"
        :invalid="submitted && missing"
        rows="3"
        auto-resize
        fluid
        data-testid="cl-revise-reason"
      />
      <small v-if="submitted && missing" class="error">{{ t('checklists.revise.reasonRequired') }}</small>
    </form>
    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
      <Button
        :label="t('checklists.revise.submit')"
        icon="mdi mdi-file-replace-outline"
        :loading="busy"
        data-testid="cl-revise-submit"
        @click="submit"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.revise-form {
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
