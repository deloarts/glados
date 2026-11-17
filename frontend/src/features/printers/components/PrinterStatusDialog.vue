<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { getPrinterStatus } from '../api/getPrinterStatus'
import { extractApiError } from '@/core/utils/errors'

import type { PrinterResponse } from '../types/printerResponse'

interface Props {
  printer?: PrinterResponse | null
}

const props = defineProps<Props>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()

const loading = ref(false)
const errorMessage = ref<string | null>(null)
const identity = ref<string | null>(null)
const statusLines = ref<string[]>([])

watch(visible, async (isVisible) => {
  if (!isVisible || !props.printer) return

  loading.value = true
  errorMessage.value = null
  identity.value = null
  statusLines.value = []

  try {
    const result = await getPrinterStatus(props.printer.id)
    identity.value = result.identity
    statusLines.value = result.status_lines
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('printers.status.errors.unreachable')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('printers.status.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <div v-if="loading" class="status-loading">
      <ProgressSpinner style="width: 2rem; height: 2rem" />
    </div>
    <Message v-else-if="errorMessage" severity="error">{{ errorMessage }}</Message>
    <div v-else class="status-content">
      <div class="status-block">
        <span class="status-label">{{ t('printers.status.identity') }}</span>
        <pre class="status-pre">{{ identity }}</pre>
      </div>
      <div class="status-block">
        <span class="status-label">{{ t('printers.status.status') }}</span>
        <pre class="status-pre">{{ statusLines.join('\n') }}</pre>
      </div>
    </div>
  </Dialog>
</template>

<style scoped lang="scss">
.status-loading {
  display: flex;
  justify-content: center;
  padding: var(--space-6) 0;
}

.status-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.status-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.status-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.status-pre {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  font-family: monospace;
  font-size: var(--font-size-sm);
  white-space: pre-wrap;
}
</style>
