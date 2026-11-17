<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatDecimal } from '@/core/utils/numbers'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { ItemUsageRow } from '../types/itemDetail'

defineProps<{
  rows: ItemUsageRow[]
  loading: boolean
  error: boolean
}>()

const emit = defineEmits<{ 'open-order': [orderId: number] }>()

const { t, te } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

// Translated through resources.projects.status, falling back to the raw
// value.
function projectStatusLabel(status: string | null): string {
  if (!status) return getEmptyPlaceholder()
  const key = `resources.projects.status.${status}`
  return te(key) ? t(key) : status
}
</script>

<template>
  <Panel :header="t('catalogue.itemDetail.cards.usedIn')">
    <div class="card-scroll-body">
      <div v-if="loading && rows.length === 0" class="loading-state">
        <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
      </div>
      <div v-else-if="error" class="error-state">
        <i class="mdi mdi-alert-outline" aria-hidden="true" />
        {{ t('catalogue.itemDetail.sectionError') }}
      </div>
      <DataTable
        v-else
        :value="rows"
        size="small"
        :show-gridlines="isTableGridlinesEnabled"
        :striped-rows="isTableStripedEnabled"
      >
        <template #empty>
          <EmptyState :message="t('catalogue.itemDetail.usedIn.empty')" />
        </template>
        <Column :header="t('catalogue.itemDetail.usedIn.columns.project')" style="width: 11rem">
          <template #body="{ data }">
            <div class="project-cell">
              <span class="project-number">{{ (data as ItemUsageRow).projectNumber }}</span>
              <span v-if="(data as ItemUsageRow).projectCustomer" class="project-customer">{{
                (data as ItemUsageRow).projectCustomer
              }}</span>
            </div>
          </template>
        </Column>
        <Column :header="t('catalogue.itemDetail.usedIn.columns.product')" style="width: 10rem">
          <template #body="{ data }">
            {{ (data as ItemUsageRow).productNumber ?? t('catalogue.itemDetail.usedIn.noProduct') }}
          </template>
        </Column>
        <Column
          field="projectDescription"
          :header="t('catalogue.itemDetail.usedIn.columns.description')"
        />
        <Column :header="t('catalogue.itemDetail.usedIn.columns.status')" style="width: 8rem">
          <template #body="{ data }">
            {{ projectStatusLabel((data as ItemUsageRow).projectStatus) }}
          </template>
        </Column>
        <Column :header="t('catalogue.itemDetail.usedIn.columns.demanded')" style="width: 7rem">
          <template #body="{ data }">{{ formatDecimal((data as ItemUsageRow).qtyDemanded) }}</template>
        </Column>
        <Column :header="t('catalogue.itemDetail.usedIn.columns.fulfilled')" style="width: 7rem">
          <template #body="{ data }">{{ formatDecimal((data as ItemUsageRow).qtyFulfilled) }}</template>
        </Column>
        <Column :header="t('catalogue.itemDetail.usedIn.columns.orders')" style="width: 12rem">
          <template #body="{ data }">
            <span v-if="(data as ItemUsageRow).fulfilledOrders.length === 0" class="orders-empty">{{
              t('catalogue.itemDetail.usedIn.noOrders')
            }}</span>
            <span v-else class="orders-list">
              <span
                v-for="fulfilledOrder in (data as ItemUsageRow).fulfilledOrders"
                :key="fulfilledOrder.orderId"
                class="order-link"
                role="button"
                tabindex="0"
                @click="emit('open-order', fulfilledOrder.orderId)"
                @keydown.enter="emit('open-order', fulfilledOrder.orderId)"
                >{{ fulfilledOrder.orderNumber }}</span
              >
            </span>
          </template>
        </Column>
      </DataTable>
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

.project-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.project-number {
  font-weight: 700;
}

.project-customer {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.orders-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.orders-empty {
  color: var(--p-text-muted-color);
}

.order-link {
  cursor: pointer;
  font-weight: 700;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}
</style>
