<script setup lang="ts">
import { ref, watch } from 'vue'

import { useUserAvatarsStore } from '@/core/stores/userAvatarsStore'

const props = defineProps<{
  userId: number
  hasAvatar: boolean
  imgClass?: string
}>()

const avatarsStore = useUserAvatarsStore()
const url = ref<string | null>(avatarsStore.get(props.userId))

async function load(): Promise<void> {
  if (!props.hasAvatar) {
    url.value = null
    return
  }
  url.value = await avatarsStore.fetch(props.userId)
}

watch(() => [props.userId, props.hasAvatar], load, { immediate: true })
</script>

<template>
  <img v-if="url" :src="url" :class="imgClass" alt="" />
  <slot v-else />
</template>
