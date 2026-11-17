<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import LotRecordPositionCard from './LotRecordPositionCard.vue'

import type {
  LotEventResponse,
  LotPositionProvisionResponse,
  LotPositionResponse,
  LotResponse,
} from '../../../types/productionLotsResponse'
import type {
  ManufacturingAssessmentResponse,
  ProductionOrderFile,
  ProductionOrderResponse,
} from '../../../types/productionOrdersResponse'
import type { OrderItemResponse, OrderResponse } from '@/features/orders'
import { sortedBySequence } from '../../../utils/sequence'

const props = defineProps<{
  lot: LotResponse
  events: LotEventResponse[]
  ordersForPosition: (positionId: number) => ProductionOrderResponse[]
  provisionsForPosition: (positionId: number) => LotPositionProvisionResponse[]
  assessmentForOrder: (orderId: number) => ManufacturingAssessmentResponse | null
  orderItemForPosition: (position: LotPositionResponse) => OrderItemResponse | null
  orderById: (orderId: number | null) => OrderResponse | null
  filesForOrder: (orderId: number) => ProductionOrderFile[]
}>()

const { t } = useI18n()

// No Panel, since the Execution tab label already names it.

const sortedPositions = computed(() =>
  sortedBySequence(props.lot.positions),
)
</script>

<template>
  <div class="execution">
    <div class="position-strip">
      <template v-for="(position, index) in sortedPositions" :key="position.id">
        <i v-if="index > 0" class="mdi mdi-chevron-right position-arrow" />
        <LotRecordPositionCard
          :position="position"
          :orders="ordersForPosition(position.id)"
          :provisions="provisionsForPosition(position.id)"
          :order-item="orderItemForPosition(position)"
          :order="orderById(position.order_id ?? null)"
          :assessment-for-order="assessmentForOrder"
          :files-for-order="filesForOrder"
          :events="events"
        />
      </template>
      <div v-if="sortedPositions.length === 0" class="empty-note">
        {{ t('production.lots.detail.positions.empty') }}
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.execution {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
}

// Positions run in sequence, so a horizontal strip reads as a pipeline.
// flex: 1 and min-height: 0 absorb the panel height, and align-items:
// stretch sizes every card to it.
.position-strip {
  flex: 1;
  // Below the execution area's floor, so the strip never overflows it.
  min-height: 9rem;
  // Lets the strip be narrower than its cards so it can scroll.
  min-width: 0;
  display: flex;
  align-items: stretch;
  gap: var(--space-3);
  overflow-x: auto;
  padding-bottom: var(--space-2);
}

.position-arrow {
  align-self: center;
  flex: 0 0 auto;
  font-size: var(--font-size-xl);
  color: var(--p-text-muted-color);
}
</style>
