<script setup lang="ts">
import { useSourceItemsAllocationsStore } from '../stores/sourceItemsAllocationsStore'
import DemandFulfillFromStockDialog from '@/shared/components/demands/DemandFulfillFromStockDialog.vue'

import { formatUnit } from '@/shared/utils/units'
import type { SourceItemDemandResponse } from '@/features/source-items'

const props = defineProps<{
  demand: SourceItemDemandResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  fulfilled: []
}>()

const allocationsStore = useSourceItemsAllocationsStore()
</script>

<template>
  <DemandFulfillFromStockDialog
    v-model:visible="visible"
    :demand="props.demand"
    :operations="allocationsStore"
    i18n-prefix="sourceItems.demands"
    :format-unit="formatUnit"
    @fulfilled="emit('fulfilled')"
  />
</template>
