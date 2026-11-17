<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatDecimal } from '@/core/utils/numbers'
import { formatISODateTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import { getLotMaterialReceipts } from '../../api/getLotMaterialReceipts'
import type { LotMaterialReceiptResponse } from '../../../types/productionLotsResponse'

// The genealogy of the lot's raw material: every receipt on the order lines
// that supply it, with the batch or heat number, delivery note and
// certificate the receiver recorded.

const props = defineProps<{
  lotId: number
}>()

const { t } = useI18n()

const receipts = ref<LotMaterialReceiptResponse[]>([])
const loading = ref(false)

async function load(lotId: number): Promise<void> {
  loading.value = true
  try {
    receipts.value = await getLotMaterialReceipts(lotId)
  } catch {
    receipts.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => props.lotId,
  (lotId) => void load(lotId),
  { immediate: true },
)
</script>

<template>
  <Panel
    :header="t('production.lots.detail.record.materialReceipts.title')"
    :pt="{ header: { 'data-testid': 'record-card-header' } }"
  >
    <div class="card-scroll-body">
      <div v-if="loading && receipts.length === 0" class="receipt-skeleton">
        <Skeleton v-for="n in 2" :key="n" height="2rem" />
      </div>
      <div v-else-if="receipts.length === 0" class="empty-note">
        {{ t('production.lots.detail.record.materialReceipts.none') }}
      </div>
      <DataTable v-else :value="receipts" data-key="delivery_id" size="small">
        <Column :header="t('production.lots.detail.record.materialReceipts.date')">
          <template #body="{ data }">
            {{ formatISODateTime((data as LotMaterialReceiptResponse).delivery_date) }}
          </template>
        </Column>
        <Column
          field="order_number"
          :header="t('production.lots.detail.record.materialReceipts.order')"
        />
        <Column :header="t('production.lots.detail.record.materialReceipts.quantity')">
          <template #body="{ data }">
            {{ formatDecimal((data as LotMaterialReceiptResponse).quantity) }}
            <Tag
              v-if="(data as LotMaterialReceiptResponse).corrects_delivery_id"
              :value="t('production.lots.detail.record.materialReceipts.correction')"
              severity="warn"
            />
          </template>
        </Column>
        <Column :header="t('production.lots.detail.record.materialReceipts.batch')">
          <template #body="{ data }">
            {{ (data as LotMaterialReceiptResponse).supplier_batch ?? getEmptyPlaceholder() }}
          </template>
        </Column>
        <Column :header="t('production.lots.detail.record.materialReceipts.deliveryNote')">
          <template #body="{ data }">
            {{
              (data as LotMaterialReceiptResponse).delivery_note_number ?? getEmptyPlaceholder()
            }}
          </template>
        </Column>
        <Column :header="t('production.lots.detail.record.materialReceipts.certificate')">
          <template #body="{ data }">
            {{
              (data as LotMaterialReceiptResponse).certificate_reference ?? getEmptyPlaceholder()
            }}
          </template>
        </Column>
      </DataTable>
    </div>
  </Panel>
</template>

<style scoped lang="scss">
.receipt-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
</style>
