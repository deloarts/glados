<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { ResultDifference } from '../utils/calculationCompare'

const props = defineProps<{
  differences: ResultDifference[]
  savedEngineVersion: number
}>()

const { t } = useI18n()

const SHOWN = 8

const rows = computed(() => props.differences.slice(0, SHOWN))
const hidden = computed(() => Math.max(0, props.differences.length - SHOWN))

function show(value: unknown): string {
  if (value === undefined || value === null) return '–'
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}
</script>

<template>
  <Message severity="warn" data-testid="calc-drift">
    <div class="drift">
      <p class="drift-text">{{ t('tools.calculations.drift.message', { version: savedEngineVersion }) }}</p>
      <table class="drift-table">
        <thead>
          <tr>
            <th>{{ t('tools.calculations.drift.value') }}</th>
            <th>{{ t('tools.calculations.drift.saved') }}</th>
            <th>{{ t('tools.calculations.drift.current') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.path">
            <td class="drift-path">{{ row.path }}</td>
            <td>{{ show(row.saved) }}</td>
            <td>{{ show(row.current) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="hidden > 0" class="drift-more">{{ t('tools.calculations.drift.more', { count: hidden }) }}</p>
    </div>
  </Message>
</template>

<style scoped lang="scss">
.drift {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.drift-text,
.drift-more {
  margin: 0;
}

.drift-table {
  border-collapse: collapse;
  font-size: var(--font-size-sm);

  th,
  td {
    text-align: left;
    padding: var(--space-1) var(--space-3) var(--space-1) 0;
  }
}

.drift-path {
  font-family: monospace;
}
</style>
