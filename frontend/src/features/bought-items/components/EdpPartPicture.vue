<script setup lang="ts">
// A Data Portal part's product picture, fetched through Glados as a blob
// (the browser loads images from its own origin only) and shown with the
// shared thumbnail cell; a missing or failed picture shows the placeholder.
// The picture route needs use:data_portal, so without it the placeholder
// shows and nothing is requested.
import { onUnmounted, ref, watch } from 'vue'

import { Permission } from '@/core/auth/permissions'
import ThumbnailCell from '@/core/components/ThumbnailCell.vue'
import { usePermissions } from '@/core/composables/usePermissions'
import { getEdpPartPicture } from '../api/boughtItemsEdpApi'

const props = withDefaults(defineProps<{ partId: number; size?: string; alt?: string }>(), {
  size: '3rem',
  alt: undefined,
})

const { hasPermission } = usePermissions()
const src = ref<string | null>(null)
let current = 0

function revoke(): void {
  if (src.value) URL.revokeObjectURL(src.value)
  src.value = null
}

watch(
  () => props.partId,
  async (partId) => {
    const request = ++current
    revoke()
    if (!hasPermission(Permission.USE_DATA_PORTAL)) return
    try {
      const blob = await getEdpPartPicture(partId)
      if (request === current && blob) src.value = URL.createObjectURL(blob)
    } catch {
      // The placeholder stays; a picture is never essential.
    }
  },
  { immediate: true },
)

onUnmounted(revoke)
</script>

<template>
  <ThumbnailCell :src="src" :size="size" :item-name="alt" />
</template>
