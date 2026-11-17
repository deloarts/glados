<script setup lang="ts">
import { computed } from 'vue'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import SourceItemDemandsControls from '../components/SourceItemDemandsControls.vue'
import SourceItemDemandsViews from '../components/SourceItemDemandsViews.vue'
import SourceItemDemandsTable from '../components/SourceItemDemandsTable.vue'
import SourceItemDemandsManageOrder from '../components/SourceItemDemandsManageOrder.vue'
import SourceItemDemandsManageStock from '../components/SourceItemDemandsManageStock.vue'
import SourceItemDemandsManageQuote from '../components/SourceItemDemandsManageQuote.vue'
import { useSourceItemDemandsFiltersStore } from '../stores/sourceItemDemandsFiltersStore'
import { useResizablePanelWidth } from '@/shared/composables/useResizablePanelWidth'
import PanelResizeHandle from '@/shared/components/layout/PanelResizeHandle.vue'

const { hasPermission } = usePermissions()
const canWriteOrders = computed(() => hasPermission(Permission.WRITE_ORDERS))
const canWriteAllocations = computed(() => hasPermission(Permission.WRITE_ALLOCATIONS))
const filtersStore = useSourceItemDemandsFiltersStore()

const {
  width: panelWidth,
  isResizing,
  min: panelMin,
  onResizeStart,
  onResizeKey,
} = useResizablePanelWidth({ defaultWidth: 360, min: 220 })
</script>

<template>
  <PageLayout
    :class="{ 'is-resizing-ew': isResizing }"
    data-class="bid-view-data"
  >
    <template #controls>
      <SourceItemDemandsControls />
    </template>
    <template #views>
      <SourceItemDemandsViews />
    </template>

    <template
      v-if="
        (canWriteOrders && filtersStore.showManageOrderPanel) ||
        (canWriteOrders && filtersStore.showManageQuotePanel) ||
        (canWriteAllocations && filtersStore.showManageStockPanel)
      "
      #panels
    >
      <SourceItemDemandsManageOrder
        v-if="canWriteOrders && filtersStore.showManageOrderPanel"
        :style="{ width: panelWidth + 'px' }"
      />
      <SourceItemDemandsManageQuote
        v-else-if="canWriteOrders && filtersStore.showManageQuotePanel"
        :style="{ width: panelWidth + 'px' }"
      />
      <SourceItemDemandsManageStock
        v-else-if="canWriteAllocations && filtersStore.showManageStockPanel"
        :style="{ width: panelWidth + 'px' }"
      />
      <PanelResizeHandle :width="panelWidth" :min="panelMin" @start="onResizeStart" @key="onResizeKey" />
    </template>
    <SourceItemDemandsTable />
  </PageLayout>
</template>

<style scoped lang="scss">
.is-resizing-ew {
  user-select: none;
  cursor: ew-resize;
}

:deep(.bid-view-data) {
  display: flex;
  flex-direction: row;
  gap: var(--space-1);
}
</style>
