<script setup lang="ts">
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import type { BoughtItemResponse } from '../../types/boughtItemsResponse'

defineProps<{
  item: BoughtItemResponse
}>()
</script>

<template>
  <span>{{ item.revision ?? getEmptyPlaceholder() }}</span>
</template>
