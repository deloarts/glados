<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { CalculationSummaryResponse } from '../types/calculation'
import LoadCalculationTable from './LoadCalculationTable.vue'

/** Picks a saved calculation of the current tool to open. */

defineProps<{
  tool: string
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{ select: [calculation: CalculationSummaryResponse] }>()

const { t } = useI18n()

function pick(row: CalculationSummaryResponse): void {
  visible.value = false
  emit('select', row)
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('tools.calculations.load.title')"
    :style="{ width: 'var(--dialog-width-lg)' }"
    :breakpoints="{ '960px': '95vw' }"
  >
    <LoadCalculationTable :tool="tool" @select="pick" />
  </Dialog>
</template>
