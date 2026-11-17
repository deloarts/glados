<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { AgentBadge } from '@/features/agents'
import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

defineProps<{
  lot: LotSummaryResponse
}>()

const { t } = useI18n()
</script>

<template>
  <i
    v-if="lot.origin_lot_id"
    class="mdi mdi-source-branch lineage-icon"
    v-tooltip.top="t(`production.lots.columns.lineageIconTooltip.${lot.origin_disposition}`)"
  />{{ lot.lot_number }}<AgentBadge kind="lot" :public-id="lot.public_id" />
</template>

<style scoped lang="scss">
.lineage-icon {
  margin-right: var(--space-1);
  color: var(--p-text-muted-color);
}
</style>
