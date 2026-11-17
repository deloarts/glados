<script setup lang="ts">
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import type { TokenStoreInstance } from '@/shared/stores/createTokenStore'

const props = defineProps<{
  store: TokenStoreInstance
}>()
</script>

<template>
  <ViewsBar
    id-prefix="tokens"
    hide-views-toggle
    :has-active-filters="false"
    @sync="props.store.triggerRefresh()"
  >
    <!-- Surface-specific buttons (e.g. the API keys docs toggle) go here. -->
    <template #start-extra><slot name="start-extra" /></template>
    <!-- Far right of the bar, where the handbook button lives by convention. -->
    <template #end><slot name="end" /></template>
  </ViewsBar>
</template>
