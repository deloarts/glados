<script setup lang="ts">
import { getMadeItemMergeTargets } from '../api/getMadeItemMergeTargets'
import { useMadeItemsStore } from '../stores/madeItemsStore'
import { useMadeItemLabel } from '../utils/madeItemLabel'
import ItemMergeDialog from '@/shared/components/items/ItemMergeDialog.vue'
import MadeItemSelect from './MadeItemSelect.vue'

import type { MadeItemResponse } from '../types/madeItemsResponse'

const props = defineProps<{
  item: MadeItemResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const store = useMadeItemsStore()
const { format: madeItemLabel } = useMadeItemLabel()

function itemLabel(item: MadeItemResponse): string {
  return madeItemLabel(item.part_number, item.revision)
}
</script>

<template>
  <ItemMergeDialog
    v-model:visible="visible"
    :item="props.item"
    :operations="store"
    :fetch-targets="getMadeItemMergeTargets"
    i18n-prefix="madeItems.catalogue.merge"
    :item-label="itemLabel"
  >
    <template
      #target-select="{ targetItem, setTargetItem, excludeId, fetchOptions, disabledReason, inputId, labelId }"
    >
      <MadeItemSelect
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
