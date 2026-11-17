<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import BoughtItemsCatalogueControls from '../components/BoughtItemsCatalogueControls.vue'
import BoughtItemsCatalogueViews from '../components/BoughtItemsCatalogueViews.vue'
import BoughtItemsCatalogueTable from '../components/BoughtItemsCatalogueTable.vue'
import BoughtItemsCatalogueEdit from '../components/BoughtItemsCatalogueEdit.vue'
import { useBoughtItemsCatalogueEditStore } from '../stores/boughtItemsCatalogueEditStore'
import { useBoughtItemsStore } from '../stores/boughtItemsStore'
import { usePdmPreviewStore } from '@/shared/pdm-preview/pdmPreviewStore'
import PdmPreviewPanel from '@/shared/pdm-preview/PdmPreviewPanel.vue'
import { useResizablePanelWidth } from '@/shared/composables/useResizablePanelWidth'
import PanelResizeHandle from '@/shared/components/layout/PanelResizeHandle.vue'

const editStore = useBoughtItemsCatalogueEditStore()
const boughtItemsStore = useBoughtItemsStore()
const pdmPreviewStore = usePdmPreviewStore()

const showPdmPreview = ref(false)

// Loaded on mount, and again whenever the table's own refresh fires; see
// MadeItemCatalogueView.vue's identical comment for the reasoning.
onMounted(() => {
  void pdmPreviewStore.load('bought')
})
watch(
  () => boughtItemsStore.refreshTrigger,
  () => void pdmPreviewStore.load('bought'),
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
    data-class="bic-view-data"
  >
    <template #controls>
      <BoughtItemsCatalogueControls @toggle-pdm-preview="showPdmPreview = !showPdmPreview" />
    </template>
    <template #views>
      <BoughtItemsCatalogueViews />
    </template>

    <template v-if="editStore.editMode" #panels>
      <BoughtItemsCatalogueEdit :style="{ width: editWidth + 'px' }" />
      <PanelResizeHandle :width="editWidth" :min="editWidthMin" @start="onEditResizeStart" @key="onEditResizeKey" />
    </template>
    <PdmPreviewPanel v-if="showPdmPreview" kind="bought" class="pdm-preview-panel" />
    <BoughtItemsCatalogueTable />
  </PageLayout>
</template>

<style scoped lang="scss">
// Not :deep(): the fallthrough class lands on PageLayout's root
// element, which Vue's scoped-CSS also stamps with this component's own
// scope id (documented root-passthrough behavior), so a plain selector
// reaches it directly.
.is-resizing-ew {
  user-select: none;
  cursor: ew-resize;
}

.pdm-preview-panel {
  margin-bottom: var(--space-3);
}

:deep(.bic-view-data) {
  display: flex;
  flex-direction: row;
  gap: var(--space-1);
}
</style>
