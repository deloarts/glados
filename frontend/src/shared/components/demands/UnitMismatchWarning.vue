<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { formatUnit } from '@/shared/utils/units'

// Warns that a demand draws on an order line of another unit, which the
// backend allows without converting; the parent decides when to show it.
defineProps<{
  demandUnit: string
  lineUnit: string
}>()

const { t } = useI18n()
</script>

<template>
  <Message severity="warn" :closable="false" size="small" class="unit-mismatch">
    <i class="mdi mdi-scale-unbalanced" aria-hidden="true" />
    {{ t('procurement.unitMismatch', { demand: formatUnit(demandUnit), line: formatUnit(lineUnit) }) }}
  </Message>
</template>

<style scoped>
.unit-mismatch {
  margin-top: var(--space-1);
}
</style>
