<script setup lang="ts">
// A minimal "are you sure" dialog for actions that need a beat before they
// run: a header, one sentence, dismiss/confirm. Deliberately a plain Dialog
// rather than OpenVue's ConfirmDialog/useConfirm: that one needs
// ConfirmationService installed at the app root and throws at setup when it
// isn't, which makes every consumer (and every consumer's test mount)
// depend on it. This has no such requirement, so a table can offer a
// confirm without changing what it takes to mount it.
import { useI18n } from 'vue-i18n'

withDefaults(
  defineProps<{
    header: string
    message: string
    confirmLabel: string
    /**
     * Falls back to common.cancel; pass something else when "Cancel" would
     * read as the action itself (e.g. a dialog that cancels demands).
     */
    dismissLabel?: string
    confirmSeverity?: 'danger' | 'primary' | 'warn'
  }>(),
  { dismissLabel: undefined, confirmSeverity: 'danger' },
)

const emit = defineEmits<{ confirm: [] }>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()

function onConfirm(): void {
  visible.value = false
  emit('confirm')
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :header="header" :style="{ width: 'var(--dialog-width-sm)' }">
    <p class="confirm-message">{{ message }}</p>

    <template #footer>
      <Button
        :label="dismissLabel ?? t('common.cancel')"
        severity="secondary"
        outlined
        @click="visible = false"
      />
      <Button :label="confirmLabel" :severity="confirmSeverity" @click="onConfirm" />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.confirm-message {
  margin: 0;
  line-height: 1.5;
}
</style>
