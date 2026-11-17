<script setup lang="ts">
import { computed } from 'vue'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import BoughtItemsDemandsControls from '../components/BoughtItemsDemandsControls.vue'
import BoughtItemsDemandsViews from '../components/BoughtItemsDemandsViews.vue'
import BoughtItemsDemandsTable from '../components/BoughtItemsDemandsTable.vue'
import BoughtItemsDemandsManageOrder from '../components/BoughtItemsDemandsManageOrder.vue'
import BoughtItemsDemandsManageStock from '../components/BoughtItemsDemandsManageStock.vue'
import BoughtItemsDemandsManageQuote from '../components/BoughtItemsDemandsManageQuote.vue'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useBoughtItemsDemandsFiltersStore } from '../stores/boughtItemsDemandsFiltersStore'
import { useResizablePanelWidth } from '@/shared/composables/useResizablePanelWidth'
import PanelResizeHandle from '@/shared/components/layout/PanelResizeHandle.vue'

const { hasPermission } = usePermissions()
const canWrite = computed(() => hasPermission(Permission.WRITE_ORDERS))
const canWriteAllocations = computed(() => hasPermission(Permission.WRITE_ALLOCATIONS))
const filtersStore = useBoughtItemsDemandsFiltersStore()

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
      <BoughtItemsDemandsControls />
    </template>
    <template #views>
      <BoughtItemsDemandsViews />
    </template>

    <template
      v-if="
        (canWrite && filtersStore.showManageOrderPanel) ||
        (canWrite && filtersStore.showManageQuotePanel) ||
        (canWriteAllocations && filtersStore.showManageStockPanel)
      "
      #panels
    >
      <BoughtItemsDemandsManageOrder
        v-if="canWrite && filtersStore.showManageOrderPanel"
        :style="{ width: panelWidth + 'px' }"
      />
      <BoughtItemsDemandsManageQuote
        v-else-if="canWrite && filtersStore.showManageQuotePanel"
        :style="{ width: panelWidth + 'px' }"
      />
      <BoughtItemsDemandsManageStock
        v-else-if="canWriteAllocations && filtersStore.showManageStockPanel"
        :style="{ width: panelWidth + 'px' }"
      />
      <PanelResizeHandle :width="panelWidth" :min="panelMin" @start="onResizeStart" @key="onResizeKey" />
    </template>
    <BoughtItemsDemandsTable />
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
