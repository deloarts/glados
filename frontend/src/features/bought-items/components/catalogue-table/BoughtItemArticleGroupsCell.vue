<script setup lang="ts">
import type { BoughtItemResponse } from '../../types/boughtItemsResponse'
import LabelTag from '@/shared/components/labels/LabelTag.vue'

defineProps<{
  item: BoughtItemResponse
}>()
</script>

<template>
  <div class="article-groups-cell">
    <LabelTag
      v-for="group in item.article_groups"
      :key="group.id"
      :label="group"
    />
  </div>
</template>

<style scoped lang="scss">
.article-groups-cell {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
</style>
