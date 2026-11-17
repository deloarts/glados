<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import type { DataTableRowClickEvent } from 'openvue/datatable'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatDateOrDash } from '@/core/utils/dates'
import { lotStatusSeverity } from '@/features/production'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { LotSummaryResponse } from '@/features/production'

defineProps<{
  lots: LotSummaryResponse[]
  loading: boolean
  error: boolean
  truncated: boolean
  limit: number
}>()

const emit = defineEmits<{ 'open-lot': [id: number] }>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

function onRowClick(event: DataTableRowClickEvent): void {
  emit('open-lot', (event.data as LotSummaryResponse).id)
}
</script>

<template>
  <Panel :header="t('catalogue.itemDetail.cards.lots')">
    <div class="card-scroll-body">
      <div v-if="loading && lots.length === 0" class="loading-state">
        <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
      </div>
      <div v-else-if="error" class="error-state">
        <i class="mdi mdi-alert-outline" aria-hidden="true" />
        {{ t('catalogue.itemDetail.sectionError') }}
      </div>
      <template v-else>
        <DataTable
          :value="lots"
          size="small"
          :show-gridlines="isTableGridlinesEnabled"
          :striped-rows="isTableStripedEnabled"
          @row-click="onRowClick"
        >
          <template #empty>
            <EmptyState :message="t('catalogue.itemDetail.lots.empty')" />
          </template>
          <Column
            field="lot_number"
            :header="t('catalogue.itemDetail.lots.columns.lotNumber')"
            style="width: 10rem"
          >
            <template #body="{ data }">
              <span class="lot-link">{{ (data as LotSummaryResponse).lot_number }}</span>
            </template>
          </Column>
          <Column :header="t('catalogue.itemDetail.lots.columns.status')" style="width: 9rem">
            <template #body="{ data }">
              <Tag
                :value="t(`production.lots.status.${(data as LotSummaryResponse).status}`)"
                :severity="lotStatusSeverity[(data as LotSummaryResponse).status]"
              />
            </template>
          </Column>
          <Column :header="t('catalogue.itemDetail.lots.columns.quantity')" style="width: 8rem">
            <template #body="{ data }">
              {{ (data as LotSummaryResponse).quantity_completed }} /
              {{ (data as LotSummaryResponse).quantity }}
            </template>
          </Column>
          <Column
            field="project_number"
            :header="t('catalogue.itemDetail.lots.columns.project')"
            style="width: 9rem"
          />
          <Column
            :header="t('catalogue.itemDetail.lots.columns.requiredDelivery')"
            style="width: 9rem"
          >
            <template #body="{ data }">
              {{ formatDateOrDash((data as LotSummaryResponse).required_delivery_date) }}
            </template>
          </Column>
          <Column :header="t('catalogue.itemDetail.lots.columns.created')" style="width: 9rem">
            <template #body="{ data }">
              {{ formatDateOrDash((data as LotSummaryResponse).created) }}
            </template>
          </Column>
        </DataTable>
        <div v-if="truncated" class="truncated-state">
          {{ t('catalogue.itemDetail.truncated', { limit }) }}
        </div>
      </template>
    </div>
  </Panel>
</template>

<style scoped lang="scss">
.loading-state {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
  font-size: var(--font-size-2xl);
  color: var(--p-text-muted-color);
}

.error-state {
  padding: var(--space-5) 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.truncated-state {
  padding: var(--space-2) var(--space-1) 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
}

.lot-link {
  font-weight: 700;
}
</style>
