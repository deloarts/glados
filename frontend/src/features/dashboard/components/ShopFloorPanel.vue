<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import PanelLoading from './PanelLoading.vue'

import { productionOrderStatusSeverity } from '@/features/production'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import type { ProductionOrderResponse } from '@/features/production'

const props = defineProps<{
  overdueOrders: ProductionOrderResponse[]
  todayOrders: ProductionOrderResponse[]
  loading: boolean
}>()

const { t } = useI18n()
const { openLotDetail } = useLotDetail()

const rows = computed(() => [...props.overdueOrders, ...props.todayOrders])

function isOverdue(order: ProductionOrderResponse): boolean {
  return props.overdueOrders.includes(order)
}

function openLot(order: ProductionOrderResponse): void {
  openLotDetail(order.lot_id)
}
</script>

<template>
  <div class="card shop-floor-panel">
    <div class="panel-title">
      <i class="mdi mdi-factory" aria-hidden="true" />
      <span>{{ t('dashboard.shopFloor.title') }}</span>
    </div>

    <PanelLoading v-if="loading && rows.length === 0" class="panel-loading" />

    <div v-else-if="rows.length === 0" class="panel-empty">
      <i class="mdi mdi-check-circle-outline panel-empty-icon" aria-hidden="true" />
      <span>{{ t('dashboard.shopFloor.empty') }}</span>
    </div>

    <ul v-else class="shop-floor-list">
      <li v-for="order in rows" :key="order.id">
        <button
          type="button"
          class="shop-floor-row"
          :class="{ 'shop-floor-row--overdue': isOverdue(order) }"
          @click="openLot(order)"
        >
          <div class="shop-floor-row-main">
            <span class="shop-floor-lot">{{ order.lot_number }}</span>
            <span class="shop-floor-machine">{{
              order.machine_internal_name || t('productionQueue.board.noMachine')
            }}</span>
          </div>
          <Tag
            :severity="productionOrderStatusSeverity[order.status]"
            :value="t(`productionQueue.status.${order.status}`)"
          />
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped lang="scss">
.shop-floor-panel {
  gap: var(--space-3);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.panel-loading,
.panel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--p-text-muted-color);
  padding: var(--space-5) 0;
  flex: 1 1 auto;
}

.panel-empty-icon {
  font-size: var(--font-size-2xl);
  color: var(--p-green-500);
}

.shop-floor-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

.shop-floor-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--p-content-border-radius);
  border: none;
  border-left: 3px solid transparent;
  background: none;
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.15s;

  &:hover {
    background-color: var(--p-content-hover-background);
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: -2px;
  }

  &--overdue {
    border-left-color: var(--p-red-500);
  }
}

.shop-floor-row-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.shop-floor-lot {
  font-weight: 600;
  font-size: var(--font-size-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.shop-floor-machine {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
