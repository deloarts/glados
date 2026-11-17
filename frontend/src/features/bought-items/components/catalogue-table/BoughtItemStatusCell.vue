<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { BoughtItemResponse } from '../../types/boughtItemsResponse'
import { catalogueStatusTagSeverity } from '@/shared/utils/catalogueStatus'

defineProps<{
  item: BoughtItemResponse
}>()

const { t } = useI18n()
</script>

<template>
  <div class="state-cell">
    <Tag
      :value="t(`boughtItems.catalogue.status.${item.status}`)"
      :severity="catalogueStatusTagSeverity(item.status)"
    />
    <Tag
      v-if="item.archived"
      :value="t('common.archivedTag')"
      severity="warn"
      icon="mdi mdi-archive-outline"
      v-tooltip.top="t('common.archivedTagTooltip')"
    />
  </div>
</template>

<style scoped lang="scss">
.state-cell {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
</style>
