<script setup lang="ts">
import { useMadeItemsAllocationsStore } from '../stores/madeItemsAllocationsStore'
import DemandFulfillFromStockDialog from '@/shared/components/demands/DemandFulfillFromStockDialog.vue'

import { formatUnit } from '@/shared/utils/units'
import type { MadeItemDemandResponse } from '@/features/made-items'

const props = defineProps<{
  demand: MadeItemDemandResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  fulfilled: []
}>()

const allocationsStore = useMadeItemsAllocationsStore()
</script>

<template>
  <DemandFulfillFromStockDialog
    v-model:visible="visible"
    :demand="props.demand"
    :operations="allocationsStore"
    i18n-prefix="madeItems.demands"
    :format-unit="formatUnit"
    @fulfilled="emit('fulfilled')"
  />
</template>
