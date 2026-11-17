<script setup lang="ts">
import { computed } from 'vue'

import { safeHref } from '@/shared/utils/isSafeHttpUrl'

import type { BoughtItemResponse } from '../../types/boughtItemsResponse'

const props = defineProps<{
  item: BoughtItemResponse
}>()

// A weblink becomes a link only when it is an absolute http(s) URL; any other stored value shows as text.
const href = computed(() => safeHref(props.item.weblink))
</script>

<template>
  <a v-if="href" :href="href" target="_blank" rel="noopener noreferrer" class="weblink-cell" @click.stop>{{
    item.weblink
  }}</a>
  <span v-else-if="item.weblink" class="weblink-cell">{{ item.weblink }}</span>
</template>

<style scoped lang="scss">
.weblink-cell {
  color: var(--p-primary-color);
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
  max-width: 100%;

  &:hover {
    text-decoration: underline;
  }
}
</style>
