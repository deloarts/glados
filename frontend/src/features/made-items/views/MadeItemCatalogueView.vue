<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import MadeItemsCatalogueControls from '../components/MadeItemsCatalogueControls.vue'
import MadeItemsCatalogueViews from '../components/MadeItemsCatalogueViews.vue'
import MadeItemsCatalogueTable from '../components/MadeItemsCatalogueTable.vue'
import MadeItemsCatalogueEdit from '../components/MadeItemsCatalogueEdit.vue'
import { useMadeItemsCatalogueEditStore } from '../stores/madeItemsCatalogueEditStore'
import { useMadeItemsStore } from '../stores/madeItemsStore'
import { usePdmPreviewStore } from '@/shared/pdm-preview/pdmPreviewStore'
import PdmPreviewPanel from '@/shared/pdm-preview/PdmPreviewPanel.vue'
import { useResizablePanelWidth } from '@/shared/composables/useResizablePanelWidth'
import PanelResizeHandle from '@/shared/components/layout/PanelResizeHandle.vue'

const editStore = useMadeItemsCatalogueEditStore()
const madeItemsStore = useMadeItemsStore()
const pdmPreviewStore = usePdmPreviewStore()

const showPdmPreview = ref(false)

// Loaded on mount, and again whenever the table's own refresh fires (the
// same `refreshTrigger` MadeItemsCatalogueTable.vue watches to refetch
// itself), so the toggle button's count and the "newer" badges stay
// current without the preview panel needing to be open.
onMounted(() => {
  void pdmPreviewStore.load('made')
})
watch(
  () => madeItemsStore.refreshTrigger,
  () => void pdmPreviewStore.load('made'),
)

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
    data-class="mic-view-data"
  >
    <template #controls>
      <MadeItemsCatalogueControls @toggle-pdm-preview="showPdmPreview = !showPdmPreview" />
    </template>
    <template #views>
      <MadeItemsCatalogueViews />
    </template>

    <template v-if="editStore.editMode" #panels>
      <MadeItemsCatalogueEdit :style="{ width: editWidth + 'px' }" />
      <PanelResizeHandle :width="editWidth" :min="editWidthMin" @start="onEditResizeStart" @key="onEditResizeKey" />
    </template>
    <PdmPreviewPanel v-if="showPdmPreview" kind="made" class="pdm-preview-panel" />
    <MadeItemsCatalogueTable />
  </PageLayout>
</template>

<style scoped lang="scss">
.is-resizing-ew {
  user-select: none;
  cursor: ew-resize;
}

.pdm-preview-panel {
  margin-bottom: var(--space-3);
}

:deep(.mic-view-data) {
  display: flex;
  flex-direction: row;
  gap: var(--space-1);
}
</style>
