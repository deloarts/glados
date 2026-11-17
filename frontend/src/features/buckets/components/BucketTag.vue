<script setup lang="ts">
import { computed } from 'vue'

import { readableTextColor } from '@/core/utils/contrast'
import { useBucketsStore } from '../stores/bucketsStore'

import type { BucketResourceType } from '../types/bucketResponse'

const props = defineProps<{
  bucketId: number | null
  resourceType: BucketResourceType
}>()

const bucketsStore = useBucketsStore()

// Renders nothing for no bucket or an unknown id, e.g. a deleted bucket,
// since a stale tag is worse than none.
const bucket = computed(() => {
  if (props.bucketId == null) return undefined
  return bucketsStore.byId[props.resourceType][props.bucketId]
})
</script>

<template>
  <Tag
    v-if="bucket"
    :value="bucket.name"
    :style="{ background: bucket.color, color: readableTextColor(bucket.color) }"
  />
</template>
