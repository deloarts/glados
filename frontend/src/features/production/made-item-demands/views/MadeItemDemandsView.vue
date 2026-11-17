<script setup lang="ts">
import { computed } from 'vue'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import MadeItemsDemandsControls from '../components/MadeItemsDemandsControls.vue'
import MadeItemsDemandsViews from '../components/MadeItemsDemandsViews.vue'
import MadeItemsDemandsTable from '../components/MadeItemsDemandsTable.vue'
import MadeItemsDemandsManageLots from '../components/MadeItemsDemandsManageLots.vue'
import MadeItemsDemandsManageStock from '../components/MadeItemsDemandsManageStock.vue'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMadeItemsDemandsFiltersStore } from '../stores/madeItemsDemandsFiltersStore'
import { useProductionPlanning } from '@/core/composables/useProductionPlanning'
import { useResizablePanelWidth } from '@/shared/composables/useResizablePanelWidth'
import PanelResizeHandle from '@/shared/components/layout/PanelResizeHandle.vue'

const { hasPermission } = usePermissions()
const { productionPlanningEnabled } = useProductionPlanning()
const canWriteLots = computed(() => hasPermission(Permission.WRITE_LOTS))
const canWriteAllocations = computed(() => hasPermission(Permission.WRITE_ALLOCATIONS))
const filtersStore = useMadeItemsDemandsFiltersStore()

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
    data-class="mid-view-data"
  >
    <template #controls>
      <MadeItemsDemandsControls />
    </template>
    <template #views>
      <MadeItemsDemandsViews />
    </template>

    <template
      v-if="
        (productionPlanningEnabled && canWriteLots && filtersStore.showManageLotsPanel) ||
        (canWriteAllocations && filtersStore.showManageStockPanel)
      "
      #panels
    >
      <MadeItemsDemandsManageLots
        v-if="productionPlanningEnabled && canWriteLots && filtersStore.showManageLotsPanel"
        :style="{ width: panelWidth + 'px' }"
      />
      <MadeItemsDemandsManageStock
        v-else-if="canWriteAllocations && filtersStore.showManageStockPanel"
        :style="{ width: panelWidth + 'px' }"
      />
      <PanelResizeHandle :width="panelWidth" :min="panelMin" @start="onResizeStart" @key="onResizeKey" />
    </template>
    <MadeItemsDemandsTable />
  </PageLayout>
</template>

<style scoped lang="scss">
.is-resizing-ew {
  user-select: none;
  cursor: ew-resize;
}

:deep(.mid-view-data) {
  display: flex;
  flex-direction: row;
  gap: var(--space-1);
}
</style>
