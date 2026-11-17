<script setup lang="ts">
// /production/orders/:id: a minimal production order detail page so search
// results have somewhere to land. Only the detail shell, with no edit,
// print or files.
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ShareButton from '@/shared/components/resource-view/ShareButton.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'

import { getProductionOrder } from '../../lots/api/getProductionOrder'
import { productionOrderStatusSeverity } from '../../utils/productionOrderStatus'
import { usePageTitle } from '@/core/composables/usePageTitle'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'
import { apiErrorStatus } from '@/core/utils/errors'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const orderId = computed(() => Number(route.params.id))

const order = ref<ProductionOrderResponse | null>(null)
const loading = ref(true)
const notFound = ref(false)
const loadError = ref(false)

// An unknown id 404s, which shows the not-found state.
async function reload(): Promise<void> {
  const id = orderId.value
  loading.value = true
  try {
    const result = await getProductionOrder(id)
    if (orderId.value !== id) return
    order.value = result
    notFound.value = false
    loadError.value = false
  } catch (e) {
    if (orderId.value !== id) return
    if (apiErrorStatus(e) === 404) {
      order.value = null
      notFound.value = true
      loadError.value = false
    } else {
      loadError.value = true
    }
  } finally {
    if (orderId.value === id) loading.value = false
  }
}

watch(
  orderId,
  (newId, oldId) => {
    // Leaving the route fires this sync watcher before unmount, when the id
    // param is gone and the id is NaN. Nothing should load then.
    if (!Number.isInteger(newId)) return
    if (oldId !== undefined && newId !== oldId) {
      order.value = null
      notFound.value = false
      loadError.value = false
    }
    void reload()
  },
  { immediate: true, flush: 'sync' },
)

const pageHeading = computed(() =>
  order.value ? order.value.production_order_number : t('pageTitles.productionOrderDetail'),
)
const { setPageTitle } = usePageTitle()
watch(pageHeading, setPageTitle, { immediate: true })
</script>

<template>
  <PageLayout>
    <template #info>
      <InfoBar>
        <template v-if="order">
          <span class="order-number">{{ order.production_order_number }}</span>
          <span class="info-sep" />
          <Tag
            :value="t(`productionQueue.status.${order.status}`)"
            :severity="productionOrderStatusSeverity[order.status]"
          />
          <span class="info-sep" />
          <RouterLink :to="`/production/lots/${order.lot_id}`" class="lot-link">
            {{ t('production.orderDetail.lot', { number: order.lot_number }) }}
          </RouterLink>
        </template>
        <template v-else-if="loading">
          <Skeleton width="9rem" height="1.5rem" border-radius="1rem" />
          <Skeleton width="5.5rem" height="1.5rem" border-radius="1rem" />
        </template>
      </InfoBar>
    </template>

    <template #controls>
      <ControlsBar>
        <template #start>
          <Button
            icon="mdi mdi-arrow-left"
            :label="t('production.orderDetail.back')"
            severity="contrast"
            text
            @click="router.push('/production/queue')"
          />
        </template>
        <template #handbook>
          <ShareButton :public-id="order?.public_id" />
        </template>
      </ControlsBar>
    </template>

    <template #views>
      <ViewsBar
        id-prefix="production-order-detail"
        hide-views-toggle
        :syncing="loading"
        :has-active-filters="false"
        @sync="reload()"
      />
    </template>

    <div v-if="loading" class="state-center" />
    <div v-else-if="notFound" class="state-center state-message">
      <i class="mdi mdi-alert-circle-outline state-icon" aria-hidden="true" />
      <span>{{ t('production.orderDetail.notFound') }}</span>
    </div>
    <div v-else-if="loadError" class="state-center state-message">
      <i class="mdi mdi-alert-outline state-icon" aria-hidden="true" />
      <span>{{ t('production.orderDetail.loadError') }}</span>
    </div>

    <Panel v-else-if="order" :header="order.production_order_number">
      {{ t('production.orderDetail.placeholder') }}
    </Panel>
  </PageLayout>
</template>

<style scoped lang="scss">
.order-number {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.lot-link {
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

.state-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: var(--space-3);
}

.state-message {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-md);

  .state-icon {
    font-size: var(--font-size-3xl);
  }
}
</style>
