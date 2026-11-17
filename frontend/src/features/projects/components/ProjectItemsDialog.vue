<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { getDemands } from '@/features/bought-items'
import { fetchAllPages } from '@/core/api/fetchAllPages'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useErrorToast } from '@/core/composables/useErrorToast'
import EmptyState from '@/shared/components/EmptyState.vue'
import type { BoughtItemDemandResponse } from '@/features/bought-items'
import type { ProjectResponse } from '../types/projectResponse'
import { formatUnit } from '@/shared/utils/units'
import { aggregateBomRows, type BomRowBase } from '../utils/bomAggregation'

const props = defineProps<{
  visible: boolean
  project: ProjectResponse | null
}>()

const emit = defineEmits<{ 'update:visible': [boolean] }>()

const { t } = useI18n()
const { toastOnError } = useErrorToast()
const router = useRouter()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

interface ItemSummary extends BomRowBase {
  itemId: number
  articleName: string
  orderCode: string
  unit: string
}

const loading = ref(false)

watchLoadingBar(loading)
const demands = ref<BoughtItemDemandResponse[]>([])

async function loadDemands(projectId: number): Promise<void> {
  loading.value = true
  try {
    demands.value = await fetchAllPages((window) => getDemands({ project_id: projectId, ...window }))
  } finally {
    loading.value = false
  }
}

watch(
  () => props.visible,
  (visible) => {
    if (visible && props.project) {
      loadDemands(props.project.id).catch(toastOnError())
    } else {
      demands.value = []
    }
  },
)

const summaries = computed<ItemSummary[]>(() =>
  aggregateBomRows<BoughtItemDemandResponse, ItemSummary>(demands.value, {
    key: (d) => String(d.item_id),
    seed: (d, key) => ({
      key,
      itemId: d.item_id,
      articleName: d.item_article_name,
      orderCode: d.item_order_code_1,
      unit: formatUnit(d.unit),
    }),
    quantity: (d) => d.quantity,
    status: (d) => d.status,
    compare: (a, b) => a.articleName.localeCompare(b.articleName),
  }),
)

// Navigates to the full project detail page and closes the dialog behind it,
// rather than leaving it open underneath the new route.
function openProject(): void {
  if (!props.project) return
  const id = props.project.id
  emit('update:visible', false)
  void router.push(`/workspace/projects/${id}`)
}
</script>

<template>
  <Dialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    :header="
      project ? t('resources.projects.itemsDialog.title', { number: project.project_number }) : ''
    "
    modal
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <DataTable
      :value="summaries"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      scrollable
      scroll-height="28rem"
    >
      <template #empty>
        <EmptyState :message="t('resources.projects.itemsDialog.empty')" />
      </template>

      <Column
        field="articleName"
        :header="t('resources.projects.itemsDialog.articleName')"
        sortable
      />
      <Column
        field="orderCode"
        :header="t('resources.projects.itemsDialog.orderCode')"
        style="width: 12rem"
      />
      <Column
        field="qtyDemanded"
        :header="t('resources.projects.itemsDialog.qtyDemanded')"
        style="width: 9rem"
        sortable
      />
      <Column
        field="qtyFulfilled"
        :header="t('resources.projects.itemsDialog.qtyFulfilled')"
        style="width: 9rem"
        sortable
      />
      <Column field="unit" :header="t('resources.projects.itemsDialog.unit')" style="width: 6rem" />
    </DataTable>

    <template #footer>
      <Button
        :label="t('resources.projects.showDetails')"
        icon="mdi mdi-open-in-new"
        :disabled="!project"
        @click="openProject"
      />
      <Button
        :label="t('common.close')"
        severity="secondary"
        outlined
        @click="$emit('update:visible', false)"
      />
    </template>
  </Dialog>
</template>

