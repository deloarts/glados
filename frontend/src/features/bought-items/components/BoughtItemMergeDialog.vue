<script setup lang="ts">
import { getBoughtItemMergeTargets } from '../api/getBoughtItemMergeTargets'
import { useBoughtItemsStore } from '../stores/boughtItemsStore'
import ItemMergeDialog from '@/shared/components/items/ItemMergeDialog.vue'
import BoughtItemSelect from './BoughtItemSelect.vue'

import type { BoughtItemResponse } from '../types/boughtItemsResponse'

const props = defineProps<{
  item: BoughtItemResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const store = useBoughtItemsStore()

function itemLabel(item: BoughtItemResponse): string {
  return item.order_code_1
}
</script>

<template>
  <ItemMergeDialog
    v-model:visible="visible"
    :item="props.item"
    :operations="store"
    :fetch-targets="getBoughtItemMergeTargets"
    i18n-prefix="boughtItems.catalogue.merge"
    :item-label="itemLabel"
  >
    <template
      #target-select="{ targetItem, setTargetItem, excludeId, fetchOptions, disabledReason, inputId, labelId }"
    >
      <BoughtItemSelect
        :model-value="targetItem"
        :input-id="inputId"
        :aria-labelledby="labelId"
        :exclude-id="excludeId"
        :fetch-options="fetchOptions"
        :disabled-reason="disabledReason"
        fluid
        @update:model-value="setTargetItem"
      />
    </template>
  </ItemMergeDialog>
</template>
