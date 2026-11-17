<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatDecimal } from '@/core/utils/numbers'

import { getLotPositionBalances } from '../../api/getLotPositionBalances'
import type { LotPositionBalanceResponse } from '../../../types/productionLotsResponse'

// Where the pieces of each position went: arrived = good + scrap + rework +
// lost + work in process. A negative difference means more was booked than
// reached the position, which the row flags.

const props = defineProps<{
  lotId: number
}>()

const { t } = useI18n()

const balances = ref<LotPositionBalanceResponse[]>([])
const loading = ref(false)

async function load(lotId: number): Promise<void> {
  loading.value = true
  try {
    balances.value = await getLotPositionBalances(lotId)
  } catch {
    balances.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => props.lotId,
  (lotId) => void load(lotId),
  { immediate: true },
)

const QUANTITY_COLUMNS = [
  'arrived',
  'good',
  'scrap',
  'rework',
  'lost',
  'wip',
  'produced',
] as const
</script>

<template>
  <Panel
    :header="t('production.lots.detail.record.tabs.balance')"
    :pt="{ header: { 'data-testid': 'record-card-header' } }"
  >
    <div class="card-scroll-body">
      <p class="balance-hint">{{ t('production.lots.detail.record.balance.hint') }}</p>
      <div v-if="loading && balances.length === 0" class="balance-skeleton">
        <Skeleton v-for="n in 2" :key="n" height="2rem" />
      </div>
      <div v-else-if="balances.length === 0" class="empty-note">
        {{ t('production.lots.detail.record.balance.none') }}
      </div>
      <DataTable v-else :value="balances" data-key="position_id" size="small">
        <Column field="sequence" :header="t('production.lots.detail.record.balance.position')" />
        <Column
          v-for="column in QUANTITY_COLUMNS"
          :key="column"
          :header="t(`production.lots.detail.record.balance.${column}`)"
        >
          <template #body="{ data }">
            {{ formatDecimal((data as LotPositionBalanceResponse)[column]) }}
          </template>
        </Column>
        <Column :header="t('production.lots.detail.record.balance.difference')">
          <template #body="{ data }">
            <span
              v-if="(data as LotPositionBalanceResponse).difference !== 0"
              v-tooltip.top="t('production.lots.detail.record.balance.differenceHint')"
              class="difference"
            >
              {{ formatDecimal((data as LotPositionBalanceResponse).difference) }}
            </span>
            <span v-else>0</span>
          </template>
        </Column>
      </DataTable>
    </div>
  </Panel>
</template>

<style scoped lang="scss">
.balance-hint {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.balance-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.difference {
  color: var(--p-red-500);
  font-weight: 600;
}
</style>
