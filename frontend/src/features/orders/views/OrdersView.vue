<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { useRoute } from 'vue-router'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import AsyncChunkLoading from '@/shared/components/layout/AsyncChunkLoading.vue'
import OrdersControls from '../components/OrdersControls.vue'
import OrdersViews from '../components/OrdersViews.vue'
import OrdersTable from '../components/OrdersTable.vue'

const route = useRoute()
const isTimelineOpen = computed(() => route.params.tab === 'timeline')

// The @svar-ui/vue-gantt chain OrdersTimelineView pulls in is heavy and only
// needed by users who actually open the timeline tab; a static import here
// would ship it to every Orders visitor. Mirrors ProductionView.vue's
// asyncTab pattern.
const OrdersTimelineView = defineAsyncComponent({
  loader: () => import('./OrdersTimelineView.vue'),
  loadingComponent: AsyncChunkLoading,
  delay: 200,
})
</script>

<template>
  <PageLayout
    :data-class="isTimelineOpen ? 'ov-timeline-data' : 'ov-table-data'"
    :card="!isTimelineOpen"
  >
    <template #controls>
      <OrdersControls />
    </template>
    <template #views>
      <OrdersViews />
    </template>
    <OrdersTimelineView v-if="isTimelineOpen" />
    <OrdersTable v-else />
  </PageLayout>
</template>

<style scoped lang="scss">
:deep(.ov-table-data) {
  display: flex;
  flex-direction: row;
}

:deep(.ov-timeline-data) {
  overflow: visible;
}
</style>
