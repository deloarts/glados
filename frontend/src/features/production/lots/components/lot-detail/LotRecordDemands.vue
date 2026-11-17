<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { formatDecimal } from '@/core/utils/numbers'
import { useMadeItemLabel } from '@/features/made-items'

import type { LotDemandResponse } from '../../../types/productionLotsResponse'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { DEMAND_STATUS_SEVERITY } from '@/core/utils/demandStatus'

defineProps<{
  demands: LotDemandResponse[]
  loading: boolean
}>()

const { t } = useI18n()
const { format: madeItemLabel } = useMadeItemLabel()
</script>

<template>
  <Panel
    :header="t('production.lots.detail.record.demands.title')"
    :pt="{ header: { 'data-testid': 'record-card-header' } }"
  >
    <!-- The scroll card scrolls this class, so several demands scroll instead
         of clipping. -->
    <div class="card-scroll-body">
      <!-- Skeletons only on the first load, not on live refetches. -->
      <ul v-if="loading && demands.length === 0" class="demand-list">
        <li v-for="n in 2" :key="n" class="demand-entry">
          <div class="detail-grid">
            <Skeleton v-for="f in 4" :key="f" height="2.2rem" />
          </div>
        </li>
      </ul>
      <div v-else-if="demands.length === 0" class="empty-note">
        {{ t('production.lots.detail.record.demands.none') }}
      </div>
      <ul v-else class="demand-list">
        <li v-for="demand in demands" :key="demand.id" class="demand-entry">
          <div class="detail-grid">
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.demands.number')
              }}</span>
              <span class="field-value demand-number">
                #{{ demand.id }}
                <i
                  v-if="demand.high_priority"
                  class="mdi mdi-flag demand-flag"
                  aria-hidden="true"
                  v-tooltip.top="t('production.lots.detail.record.demands.highPriority')"
                />
              </span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.demands.status')
              }}</span>
              <Tag
                :value="t(`madeItems.demands.status.${demand.status}`)"
                :severity="DEMAND_STATUS_SEVERITY[demand.status]"
              />
            </div>
            <div class="field">
              <span class="field-label">{{ t('production.lots.detail.record.demands.qty') }}</span>
              <span class="field-value"
                >{{ formatDecimal(demand.allocated_quantity) }} /
                {{ formatDecimal(demand.quantity) }} {{ demand.unit }}</span
              >
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.demands.requester')
              }}</span>
              <span class="field-value">{{
                demand.creator?.full_name ?? getEmptyPlaceholder()
              }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.demands.requested')
              }}</span>
              <span class="field-value">{{ demand.created }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.demands.desiredBy')
              }}</span>
              <span class="field-value">{{
                demand.desired_delivery_date ?? getEmptyPlaceholder()
              }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{ t('production.lots.detail.record.demands.item') }}</span>
              <span class="field-value">{{
                demand.item_part_number
                  ? madeItemLabel(demand.item_part_number, demand.item_revision)
                  : demand.item_article_name
              }}</span>
            </div>
            <div class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.demands.project')
              }}</span>
              <span class="field-value">{{ demand.project_number }}</span>
            </div>
            <div v-if="demand.is_alteration" class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.demands.alterationOf')
              }}</span>
              <span class="field-value">{{
                demand.alteration_of_made_item_part_number
                  ? madeItemLabel(
                      demand.alteration_of_made_item_part_number,
                      demand.alteration_of_made_item_revision,
                    )
                  : demand.alteration_of_made_item_article_name || getEmptyPlaceholder()
              }}</span>
            </div>
            <div v-if="demand.notify_on_delivery" class="field">
              <span class="field-label">{{
                t('production.lots.detail.record.demands.notify')
              }}</span>
              <span class="field-value"><i class="mdi mdi-bell-outline" aria-hidden="true" /></span>
            </div>
            <div v-if="demand.note" class="field field-wide">
              <span class="field-label">{{ t('production.lots.detail.record.demands.note') }}</span>
              <span class="field-value field-note">{{ demand.note }}</span>
            </div>
          </div>
        </li>
      </ul>
    </div>
  </Panel>
</template>

<style scoped lang="scss">
.demand-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.demand-entry {
  &:not(:last-child) {
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--p-content-border-color);
  }
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
  gap: var(--space-3) var(--space-5);
}

.field {
  min-width: 0;
}

.field-wide {
  grid-column: 1 / -1;
}

.field-value {
  font-size: var(--font-size-sm);
}

.field-note {
  white-space: pre-line;
}

.demand-number {
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
