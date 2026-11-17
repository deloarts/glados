<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import type { DataTableRowClickEvent } from 'openvue/datatable'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { DEMAND_STATUS_SEVERITY } from '@/core/utils/demandStatus'
import { formatDecimal } from '@/core/utils/numbers'
import { formatDateOrDash } from '@/core/utils/dates'
import EmptyState from '@/shared/components/EmptyState.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'

import type { CatalogueItemKind, ItemDemandRow } from '../types/itemDetail'
import { formatUnit } from '@/shared/utils/units'

const props = defineProps<{
  kind: CatalogueItemKind
  rows: ItemDemandRow[]
  loading: boolean
  error: boolean
  truncated: boolean
  limit: number
  /** Header of the kind-specific trailing column; omitted means no column. */
  extraLabel?: string
}>()

const emit = defineEmits<{ open: [id: number] }>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

// The statuses are shared, but each kind translates them in its own
// namespace, and this card renders all three.
const STATUS_NAMESPACE: Record<CatalogueItemKind, string> = {
  bought: 'boughtItems',
  made: 'madeItems',
  source: 'sourceItems',
}

function statusLabel(status: string): string {
  return t(`${STATUS_NAMESPACE[props.kind]}.demands.status.${status}`)
}

function onRowClick(event: DataTableRowClickEvent): void {
  emit('open', (event.data as ItemDemandRow).id)
}
</script>

<template>
  <Panel :header="t('catalogue.itemDetail.cards.demands')">
    <div class="card-scroll-body">
      <!-- Spinner only on the first load, not on reloads. -->
      <div v-if="loading && rows.length === 0" class="loading-state">
        <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
      </div>
      <div v-else-if="error" class="error-state">
        <i class="mdi mdi-alert-outline" aria-hidden="true" />
        {{ t('catalogue.itemDetail.sectionError') }}
      </div>
      <template v-else>
        <DataTable
          :value="rows"
          size="small"
          :show-gridlines="isTableGridlinesEnabled"
          :striped-rows="isTableStripedEnabled"
          @row-click="onRowClick"
        >
          <template #empty>
            <EmptyState :message="t('catalogue.itemDetail.demands.empty')" />
          </template>
          <Column :header="t('catalogue.itemDetail.demands.columns.id')" style="width: 6rem">
            <template #body="{ data }">
              <span class="demand-id">
                #{{ (data as ItemDemandRow).id }}
                <i
                  v-if="(data as ItemDemandRow).highPriority"
                  class="mdi mdi-flag demand-flag"
                  aria-hidden="true"
                />
              </span>
            </template>
          </Column>
          <Column :header="t('catalogue.itemDetail.demands.columns.status')" style="width: 9rem">
            <template #body="{ data }">
              <Tag
                :value="statusLabel((data as ItemDemandRow).status)"
                :severity="DEMAND_STATUS_SEVERITY[(data as ItemDemandRow).status]"
              />
            </template>
          </Column>
          <Column :header="t('catalogue.itemDetail.demands.columns.quantity')" style="width: 8rem">
            <template #body="{ data }">
              {{ formatDecimal((data as ItemDemandRow).quantity) }}
              {{ formatUnit((data as ItemDemandRow).unit) }}
            </template>
          </Column>
          <Column
            field="projectNumber"
            :header="t('catalogue.itemDetail.demands.columns.project')"
            style="width: 9rem"
          />
          <Column
            :header="t('catalogue.itemDetail.demands.columns.desiredDelivery')"
            style="width: 9rem"
          >
            <template #body="{ data }">
              {{ formatDateOrDash((data as ItemDemandRow).desiredDeliveryDate) }}
            </template>
          </Column>
          <Column :header="t('catalogue.itemDetail.demands.columns.created')" style="width: 10rem">
            <template #body="{ data }">
              <UserDateCell
                :date="(data as ItemDemandRow).created"
                :user="(data as ItemDemandRow).creator"
                :name="(data as ItemDemandRow).creatorName"
              />
            </template>
          </Column>
          <Column v-if="extraLabel" :header="extraLabel" style="width: 10rem">
            <template #body="{ data }">
              {{ (data as ItemDemandRow).extra }}
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

.demand-id {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.demand-flag {
  color: var(--p-red-500);
  font-size: var(--font-size-sm);
}
</style>
