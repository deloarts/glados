<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatDateOrDash } from '@/core/utils/dates'
import { getLots } from '../../api/getLots'
import { lotStatusSeverity } from '../../utils/lotStatus'
import EmptyState from '@/shared/components/EmptyState.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'

import type { LotSummaryResponse } from '../../types/productionLotsResponse'
import { DEMAND_STATUS_SEVERITY } from '@/core/utils/demandStatus'
import { getMadeItemDemands } from '@/features/made-items'
import type { MadeItemDemandResponse, MadeItemResponse } from '@/features/made-items'

const props = defineProps<{
  item: MadeItemResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()

// Local, since loading them into the stores would clobber their paged state.
const demands = ref<MadeItemDemandResponse[]>([])
const lots = ref<LotSummaryResponse[]>([])
const loading = ref(false)
const failed = ref(false)

// Shows the most recent page and says when it truncates.
const PAGE_LIMIT = 100

watch([visible, () => props.item?.id], async ([isVisible]) => {
  if (!isVisible || !props.item) return

  loading.value = true
  failed.value = false
  demands.value = []
  lots.value = []

  try {
    const [demandPage, lotPage] = await Promise.all([
      getMadeItemDemands({
        made_item_id: props.item.id,
        limit: PAGE_LIMIT,
        order_by: 'created',
        order_dir: 'desc',
      }),
      getLots({
        made_item_id: props.item.id,
        limit: PAGE_LIMIT,
        order_by: 'created',
        order_dir: 'desc',
      }),
    ])
    demands.value = demandPage.items
    lots.value = lotPage.items
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      item
        ? `${t('madeItems.catalogue.history.title')}, #${item.id} ${item.article_name}`
        : t('madeItems.catalogue.history.title')
    "
    :style="{ width: 'var(--dialog-width-full)' }"
  >
    <Message v-if="failed" severity="error" :closable="false">
      {{ t('madeItems.catalogue.history.errors.load') }}
    </Message>

    <div v-else class="history-layout">
      <section>
        <h3 class="section-title">
          <i class="mdi mdi-clipboard-text-outline" aria-hidden="true" />
          {{ t('madeItems.catalogue.history.demands') }}
        </h3>
        <DataTable :value="demands" :loading="loading" size="small" scrollable scroll-height="18rem">
          <template #empty>
            <EmptyState :message="t('madeItems.catalogue.history.noDemands')" />
          </template>
          <Column field="id" :header="t('madeItems.demands.columns.id')" style="width: 5rem" />
          <Column :header="t('madeItems.demands.columns.status')" style="width: 8rem">
            <template #body="{ data }">
              <Tag
                :value="t(`madeItems.demands.status.${(data as MadeItemDemandResponse).status}`)"
                :severity="DEMAND_STATUS_SEVERITY[(data as MadeItemDemandResponse).status]"
              />
            </template>
          </Column>
          <Column :header="t('madeItems.demands.columns.quantity')" style="width: 8rem">
            <template #body="{ data }">
              {{ (data as MadeItemDemandResponse).quantity }}
              {{ (data as MadeItemDemandResponse).unit }}
            </template>
          </Column>
          <Column
            field="project_number"
            :header="t('madeItems.demands.columns.project')"
            style="width: 10rem"
          />
          <Column :header="t('madeItems.demands.columns.desiredDelivery')" style="width: 9rem">
            <template #body="{ data }">
              {{ formatDateOrDash((data as MadeItemDemandResponse).desired_delivery_date) }}
            </template>
          </Column>
          <Column :header="t('madeItems.demands.columns.created')">
            <template #body="{ data }">
              <UserDateCell
                :date="(data as MadeItemDemandResponse).created"
                :user="(data as MadeItemDemandResponse).creator"
              />
            </template>
          </Column>
        </DataTable>
      </section>

      <section>
        <h3 class="section-title">
          <i class="mdi mdi-factory" aria-hidden="true" />
          {{ t('madeItems.catalogue.history.lots') }}
        </h3>
        <DataTable :value="lots" :loading="loading" size="small" scrollable scroll-height="18rem">
          <template #empty>
            <EmptyState :message="t('madeItems.catalogue.history.noLots')" />
          </template>
          <Column
            field="lot_number"
            :header="t('production.lots.columns.lotNumber')"
            style="width: 10rem"
          />
          <Column :header="t('production.lots.columns.status')" style="width: 10rem">
            <template #body="{ data }">
              <Tag
                :value="t(`production.lots.status.${(data as LotSummaryResponse).status}`)"
                :severity="lotStatusSeverity[(data as LotSummaryResponse).status]"
              />
            </template>
          </Column>
          <Column :header="t('production.lots.columns.quantity')" style="width: 9rem">
            <template #body="{ data }">
              {{ (data as LotSummaryResponse).quantity_completed }} /
              {{ (data as LotSummaryResponse).quantity }}
            </template>
          </Column>
          <Column
            field="project_number"
            :header="t('production.lots.columns.project')"
            style="width: 10rem"
          />
          <Column :header="t('production.lots.columns.requiredDeliveryDate')" style="width: 9rem">
            <template #body="{ data }">
              {{ formatDateOrDash((data as LotSummaryResponse).required_delivery_date) }}
            </template>
          </Column>
          <Column :header="t('production.lots.columns.created')">
            <template #body="{ data }">
              <UserDateCell
                :date="(data as LotSummaryResponse).created"
                :user="(data as LotSummaryResponse).creator"
              />
            </template>
          </Column>
        </DataTable>
      </section>

      <Message
        v-if="demands.length === PAGE_LIMIT || lots.length === PAGE_LIMIT"
        severity="info"
        :closable="false"
      >
        {{ t('madeItems.catalogue.history.truncated', { limit: PAGE_LIMIT }) }}
      </Message>
    </div>
  </Dialog>
</template>

<style scoped lang="scss">
.history-layout {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.section-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-md);
  font-weight: 600;
}
</style>
