<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { HelpDrawer } from '@/shared/help'
import PendingTerminalsTable from './PendingTerminalsTable.vue'

import type { TerminalResponse } from '../types/terminalResponse'

/**
 * The terminals waiting for someone to type their pairing code, opened from
 * the controls bar. The list follows the live stream while the dialog is
 * open, so a TV that registers meanwhile shows up here at once.
 */
defineProps<{
  terminals: TerminalResponse[]
  canManage: boolean
  /** The tooltip of a disabled button, naming the missing permission. */
  missingHint: string
}>()

const emit = defineEmits<{
  approve: [terminal: TerminalResponse]
  delete: [terminal: TerminalResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const explainVisible = ref(false)
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: 'var(--dialog-width-lg)' }">
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ t('terminals.pending.title') }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('terminals.approve.help')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('terminals.approve.help')"
          @click="explainVisible = true"
        />
      </div>
    </template>

    <div class="waiting" data-testid="terminals-waiting-dialog">
      <p class="hint">{{ t('terminals.pending.hint') }}</p>
      <div class="table-wrap">
        <PendingTerminalsTable
          :terminals="terminals"
          :can-manage="canManage"
          :missing-hint="missingHint"
          @approve="emit('approve', $event)"
          @delete="emit('delete', $event)"
        />
      </div>
    </div>

    <template #footer>
      <Button :label="t('common.close')" severity="secondary" text @click="visible = false" />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="resources/terminals" anchor="approve" />
</template>

<style scoped lang="scss">
.dialog-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.dialog-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.waiting {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

// The table scrolls inside this height, so a long list keeps the dialog
// on the screen.
.table-wrap {
  display: flex;
  flex-direction: column;
  height: min(60vh, 32rem);
  min-height: 0;
}

.hint {
  margin: 0;
}
</style>
