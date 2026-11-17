<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { HelpDrawer } from '@/shared/help'

const props = defineProps<{
  visible: boolean
  lotNumber: string
  // Parent-controlled: true while its own confirm handler's mutation is in
  // flight, the dialog itself doesn't know when that settles.
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:visible': [boolean]
  confirm: [reason: string]
}>()

const { t } = useI18n()
// Opens the handbook page that explains this dialog.
const explainVisible = ref(false)
// Prefixes the ids that tie each label to its control.
const uid = useId()
const reason = ref('')

watch(
  () => props.visible,
  (visible) => {
    if (visible) reason.value = ''
  },
)

const canSubmit = computed(() => reason.value.trim().length > 0 && !props.loading)

function close(): void {
  emit('update:visible', false)
}

function onConfirm(): void {
  if (!canSubmit.value) return
  emit('confirm', reason.value.trim())
}
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-sm)' }"
    @update:visible="close"
  >
    <template #header>
      <div class="reject-source-header">
        <span class="p-dialog-title">{{ t('production.lots.detail.record.sourceApproval.rejectDialogTitle') }}</span>
        <Button
          type="button"
          class="reject-source-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('production.lots.detail.record.sourceApproval.rejectExplain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('production.lots.detail.record.sourceApproval.rejectExplain')"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <p class="lot-context">{{ lotNumber }}</p>

    <div class="field">
      <label :for="`${uid}-reason-label`">{{ t('production.lots.detail.record.sourceApproval.reasonLabel') }}</label>
      <Textarea
        v-model="reason"
        :id="`${uid}-reason-label`"
        rows="4"
        auto-resize
        fluid
        :placeholder="t('production.lots.detail.record.sourceApproval.reasonPlaceholder')"
      />
      <small class="hint">{{ t('production.lots.detail.record.sourceApproval.reasonRequired') }}</small>
    </div>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="loading"
        @click="close"
      />
      <Button
        :label="t('production.lots.detail.record.sourceApproval.reject')"
        severity="danger"
        :loading="loading"
        :disabled="!canSubmit"
        @click="onConfirm"
      />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="production/material-source" anchor="approval" />
</template>

<style scoped lang="scss">
.reject-source-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.reject-source-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.lot-context {
  margin: 0 0 var(--space-4);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.field {
  label {
    font-size: var(--font-size-sm);
    color: var(--p-text-muted-color);
  }

  .hint {
    font-size: var(--font-size-xs);
    color: var(--p-text-muted-color);
  }
}
</style>
