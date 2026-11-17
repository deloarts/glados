<script setup lang="ts">
import { useBoughtItemsAllocationsStore } from '../stores/boughtItemsAllocationsStore'
import DemandFulfillFromStockDialog from '@/shared/components/demands/DemandFulfillFromStockDialog.vue'

import { formatUnit } from '@/shared/utils/units'
import type { BoughtItemDemandResponse } from '@/features/bought-items'

const props = defineProps<{
  demand: BoughtItemDemandResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  fulfilled: []
}>()

const allocationsStore = useBoughtItemsAllocationsStore()
</script>

<template>
  <DemandFulfillFromStockDialog
    v-model:visible="visible"
    :demand="props.demand"
    :operations="allocationsStore"
    i18n-prefix="boughtItems.demands"
    :format-unit="formatUnit"
    @fulfilled="emit('fulfilled')"
  />
</template>
