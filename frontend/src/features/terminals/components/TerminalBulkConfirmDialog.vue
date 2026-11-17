<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'
import { runBulkTerminalAction, type TerminalBulkAction } from '../api/terminalsApi'

/**
 * Confirms an action on all terminals and runs it in one request. The
 * message names how many terminals it hits; revoking and deleting all of
 * them cannot be undone by a click, so they also ask to type that number.
 */
const props = defineProps<{
  action: TerminalBulkAction | null
  /** How many terminals the action hits as the list shows it now. */
  count: number
}>()

const emit = defineEmits<{ done: [action: TerminalBulkAction, count: number] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()

const ICONS: Record<TerminalBulkAction, string> = {
  reload: 'mdi mdi-refresh',
  identify: 'mdi mdi-crosshairs-gps',
  revoke: 'mdi mdi-cancel',
  delete: 'mdi mdi-delete-outline',
}

const typed = ref('')
const saving = ref(false)
const errorMessage = ref<string | null>(null)

watch(visible, (open) => {
  if (!open) return
  typed.value = ''
  errorMessage.value = null
})

const needsTyping = computed(() => props.action === 'revoke' || props.action === 'delete')
const destructive = needsTyping

const typedMatches = computed(() => typed.value.trim() === String(props.count))

const header = computed(() => (props.action ? t(`terminals.bulk.${props.action}.header`) : ''))
const message = computed(() =>
  props.action
    ? t(`terminals.bulk.${props.action}.message`, { count: props.count }, props.count)
    : '',
)
const confirmLabel = computed(() =>
  props.action ? t(`terminals.bulk.${props.action}.confirm`) : '',
)

async function onConfirm(): Promise<void> {
  const action = props.action
  if (!action || (needsTyping.value && !typedMatches.value)) return
  saving.value = true
  errorMessage.value = null
  try {
    const count = await runBulkTerminalAction(action)
    visible.value = false
    emit('done', action, count)
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('terminals.errors.unknown')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :header="header" :style="{ width: 'var(--dialog-width-sm)' }">
    <form class="dialog-body" @submit.prevent="onConfirm">
      <p class="message" data-testid="terminals-bulk-message">{{ message }}</p>
      <div v-if="needsTyping" class="field">
        <label for="terminals-bulk-typed">{{ t('terminals.bulk.typeCount', { count }) }}</label>
        <InputText
          id="terminals-bulk-typed"
          v-model="typed"
          inputmode="numeric"
          autocomplete="off"
          fluid
          autofocus
          data-testid="terminals-bulk-typed"
        />
      </div>
    </form>

    <template #footer>
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error">
        {{ errorMessage }}
      </Message>
      <Button
        type="button"
        :label="t('common.cancel')"
        severity="secondary"
        text
        :disabled="saving"
        @click="visible = false"
      />
      <Button
        :label="confirmLabel"
        :icon="action ? ICONS[action] : undefined"
        :severity="destructive ? 'danger' : undefined"
        :loading="saving"
        :disabled="needsTyping && !typedMatches"
        data-testid="terminals-bulk-confirm"
        @click="onConfirm"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.dialog-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.message {
  margin: 0;
  line-height: 1.5;
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}
</style>
