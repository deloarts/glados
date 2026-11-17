<script setup lang="ts">
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { usePdmPreviewStore } from '@/shared/pdm-preview/pdmPreviewStore'
import PdmPreviewBadge from '@/shared/pdm-preview/PdmPreviewBadge.vue'

import type { BoughtItemResponse } from '../../types/boughtItemsResponse'

defineProps<{
  item: BoughtItemResponse
}>()

const pdmPreviewStore = usePdmPreviewStore()
</script>

<template>
  <div class="part-number-cell">
    <span>{{ item.part_number ?? getEmptyPlaceholder() }}</span>
    <PdmPreviewBadge
      v-if="pdmPreviewStore.isNewer('bought', item.public_id)"
      :preview="pdmPreviewStore.isNewer('bought', item.public_id)!"
    />
  </div>
</template>

<style scoped lang="scss">
.part-number-cell {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
</style>
