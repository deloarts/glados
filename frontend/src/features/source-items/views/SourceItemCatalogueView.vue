<script setup lang="ts">

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import SourceItemsCatalogueControls from '../components/SourceItemsCatalogueControls.vue'
import SourceItemsCatalogueViews from '../components/SourceItemsCatalogueViews.vue'
import SourceItemsCatalogueTable from '../components/SourceItemsCatalogueTable.vue'
import SourceItemsCatalogueEdit from '../components/SourceItemsCatalogueEdit.vue'
import { useSourceItemsCatalogueEditStore } from '../stores/sourceItemsCatalogueEditStore'
import { useResizablePanelWidth } from '@/shared/composables/useResizablePanelWidth'
import PanelResizeHandle from '@/shared/components/layout/PanelResizeHandle.vue'

const editStore = useSourceItemsCatalogueEditStore()

// ── Edit panel resize (horizontal) ───────────────────────────────────

const {
  width: editWidth,
  isResizing: isResizingEdit,
  min: editWidthMin,
  onResizeStart: onEditResizeStart,
  onResizeKey: onEditResizeKey,
} = useResizablePanelWidth({ defaultWidth: 352, min: 200 })
</script>

<template>
  <PageLayout
    :class="{ 'is-resizing-ew': isResizingEdit }"
    data-class="bic-view-data"
  >
    <template #controls>
      <SourceItemsCatalogueControls />
    </template>
    <template #views>
      <SourceItemsCatalogueViews />
    </template>

    <template v-if="editStore.editMode" #panels>
      <SourceItemsCatalogueEdit :style="{ width: editWidth + 'px' }" />
      <PanelResizeHandle :width="editWidth" :min="editWidthMin" @start="onEditResizeStart" @key="onEditResizeKey" />
    </template>
    <SourceItemsCatalogueTable />
  </PageLayout>
</template>

<style scoped lang="scss">
.is-resizing-ew {
  user-select: none;
  cursor: ew-resize;
}

:deep(.bic-view-data) {
  display: flex;
  flex-direction: row;
  gap: var(--space-1);
}
</style>
