<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { useMadeItemsDemandsStore } from '@/features/made-items'
import type {
  CancelImpactLot,
  MadeItemDemandCancelImpact,
  MadeItemDemandResponse,
} from '@/features/made-items'


const props = defineProps<{
  demand: MadeItemDemandResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  canceled: []
}>()

const { t } = useI18n()

const demandsStore = useMadeItemsDemandsStore()

const impact = ref<MadeItemDemandCancelImpact | null>(null)
const loading = ref(false)
const { submitting, errorMessage, run } = useSubmitAction()

// immediate: the dialog may be mounted already open (v-if-free parents
// keep it in the tree), and a watcher that only fires on change would
// then never load the impact.
watch(
  visible,
  async (open) => {
    impact.value = null
    errorMessage.value = null
    if (!open || !props.demand) return

    loading.value = true
    try {
      impact.value = await demandsStore.fetchCancelImpact(props.demand.id)
    } catch (e) {
      errorMessage.value = extractApiError(e) ?? t('madeItems.demands.cancelDialog.errors.unknown')
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

/**
 * Lots that survive are shown apart from the ones that go: mixing them
 * into one list is what makes a cascade dialog unreadable.
 */
const doomedLots = computed<CancelImpactLot[]>(() =>
  (impact.value?.lots ?? []).filter((lot) => lot.will_cancel),
)
const keptLots = computed<CancelImpactLot[]>(() =>
  (impact.value?.lots ?? []).filter((lot) => !lot.will_cancel),
)

const hasImpact = computed(() => (impact.value?.lots?.length ?? 0) > 0)

const missingPermission = computed(
  () => impact.value !== null && !impact.value.can_cancel_lots,
)
// A lot that already made good pieces refuses its cancel, and the demand's
// cancel with it, until it is force-completed.
const refusingLots = computed(() => doomedLots.value.filter((lot) => lot.cancel_refused))
// The cascade is only confirmed once its impact is on screen, so a failed
// or still running impact request keeps the button disabled.
const blocked = computed(
  () => impact.value === null || missingPermission.value || refusingLots.value.length > 0,
)

async function onConfirm(): Promise<void> {
  const demand = props.demand
  if (!demand) return

  await run(async () => {
    await demandsStore.cancel(demand.id)
    emit('canceled')
    visible.value = false
  }, t('madeItems.demands.cancelDialog.errors.unknown'))
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      demand
        ? `${t('madeItems.demands.cancelDialog.title')}, ${demand.item_article_name}`
        : t('madeItems.demands.cancelDialog.title')
    "
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <div class="cancel-impact">
      <div v-if="loading" class="loading-state">
        <ProgressSpinner style="width: 2rem; height: 2rem" stroke-width="6" />
        <span>{{ t('madeItems.demands.cancelDialog.loading') }}</span>
      </div>

      <template v-else-if="impact">
        <Message v-if="missingPermission" severity="error" :closable="false">
          {{ t('madeItems.demands.cancelDialog.missingPermission') }}
        </Message>
        <Message v-if="refusingLots.length > 0" severity="error" :closable="false">
          {{
            t('madeItems.demands.cancelDialog.goodPiecesRefusal', {
              lots: refusingLots.map((lot) => lot.lot_number).join(', '),
            })
          }}
        </Message>

        <Message :severity="hasImpact ? 'warn' : 'info'" :closable="false">
          <span v-if="hasImpact">
            {{
              t('madeItems.demands.cancelDialog.warning', {
                demand: `#${impact.demand_item_id}`,
                quantity: impact.quantity,
                unit: impact.unit,
              })
            }}
          </span>
          <span v-else>{{ t('madeItems.demands.cancelDialog.noImpact') }}</span>
        </Message>

        <!-- What goes away -->
        <div v-if="doomedLots.length > 0" class="impact-section">
          <span class="section-title">
            {{ t('madeItems.demands.cancelDialog.willBeCanceled') }}
          </span>

          <div v-for="lot in doomedLots" :key="lot.lot_id" class="lot-card">
            <div class="lot-header">
              <i class="mdi mdi-factory" aria-hidden="true" />
              <span class="lot-number">{{ lot.lot_number }}</span>
              <Tag :value="lot.status" severity="secondary" />
              <span class="lot-meta">
                {{ t('madeItems.demands.cancelDialog.lotQuantity') }}: {{ lot.quantity }} ·
                {{ t('madeItems.demands.cancelDialog.allocatedHere') }}:
                {{ lot.allocated_quantity }}
              </span>
            </div>

            <ul class="impact-list">
              <li v-if="lot.source_item_demand" class="impact-row">
                <i class="mdi mdi-cube-outline" aria-hidden="true" />
                <span>
                  {{ t('madeItems.demands.cancelDialog.sourceItemDemand') }}
                  #{{ lot.source_item_demand.demand_id }} ,
                  {{ lot.source_item_demand.item_article_name }}
                  ({{ lot.source_item_demand.quantity }} {{ lot.source_item_demand.unit }})
                </span>
                <Tag
                  v-if="!lot.source_item_demand.will_cancel"
                  :value="lot.source_item_demand.keep_reason ?? ''"
                  severity="info"
                />
              </li>

              <li
                v-for="order in lot.production_orders"
                :key="order.production_order_id"
                class="impact-row"
              >
                <i class="mdi mdi-cog-outline" aria-hidden="true" />
                <span>
                  {{ t('madeItems.demands.cancelDialog.productionOrder') }}
                  {{ order.production_order_number }} ,
                  {{ t('madeItems.demands.cancelDialog.step') }}
                  {{ order.lot_position_sequence }}
                  <template v-if="order.machine_name"> · {{ order.machine_name }}</template>
                  ({{ order.quantity_completed }}/{{ order.quantity }})
                </span>
                <Tag v-if="!order.will_cancel" :value="order.keep_reason ?? ''" severity="info" />
              </li>

              <li v-for="item in lot.order_items" :key="item.order_item_id" class="impact-row">
                <i class="mdi mdi-truck-outline" aria-hidden="true" />
                <span>
                  {{ t('madeItems.demands.cancelDialog.orderItem') }}
                  {{ item.order_number }} / {{ t('madeItems.demands.cancelDialog.position') }}
                  {{ item.position }}, {{ item.item_article_name }}
                  <template v-if="item.supplier_name"> · {{ item.supplier_name }}</template>
                  ({{ item.quantity_delivered }}/{{ item.quantity }} {{ item.unit }})
                </span>
                <Tag v-if="!item.will_cancel" :value="item.keep_reason ?? ''" severity="info" />
              </li>

              <li
                v-for="item in lot.source_item_demand?.order_items ?? []"
                :key="`raw-${item.order_item_id}`"
                class="impact-row impact-row--kept"
              >
                <i class="mdi mdi-information-outline" aria-hidden="true" />
                <span>
                  {{ t('madeItems.demands.cancelDialog.rawMaterialOrder') }}
                  {{ item.order_number }} / {{ t('madeItems.demands.cancelDialog.position') }}
                  {{ item.position }}, {{ item.item_article_name }}
                  <template v-if="item.supplier_name"> · {{ item.supplier_name }}</template>
                </span>
                <Tag :value="t('madeItems.demands.cancelDialog.keptTag')" severity="info" />
              </li>
            </ul>
          </div>
        </div>

        <!-- What survives -->
        <div v-if="keptLots.length > 0" class="impact-section">
          <span class="section-title">{{ t('madeItems.demands.cancelDialog.willBeKept') }}</span>
          <div v-for="lot in keptLots" :key="lot.lot_id" class="lot-card lot-card--kept">
            <div class="lot-header">
              <i class="mdi mdi-factory" aria-hidden="true" />
              <span class="lot-number">{{ lot.lot_number }}</span>
              <Tag :value="lot.status" severity="secondary" />
            </div>
            <span class="keep-reason">
              {{ lot.keep_reason }}
              <template v-if="(lot.other_demand_ids?.length ?? 0) > 0">
                ({{ t('madeItems.demands.cancelDialog.otherDemands') }}:
                {{ lot.other_demand_ids!.map((id) => `#${id}`).join(', ') }})
              </template>
            </span>
            <span class="keep-reason">
              {{ t('madeItems.demands.cancelDialog.allocationReleased') }}
            </span>
          </div>
        </div>
      </template>

      <Message v-if="errorMessage" severity="error" :closable="false">{{ errorMessage }}</Message>
    </div>

    <template #footer>
      <Button :label="t('common.close')" severity="secondary" outlined @click="visible = false" />
      <Button
        :label="t('madeItems.demands.cancelDialog.confirm')"
        icon="mdi mdi-close-circle-outline"
        severity="danger"
        :loading="submitting"
        :disabled="blocked"
        @click="onConfirm"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.cancel-impact {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.loading-state {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-5);
  justify-content: center;
  color: var(--p-text-muted-color);
}

.impact-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.section-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--p-text-muted-color);
}

.lot-card {
  border: 1px solid var(--p-content-border-color);
  border-left: 3px solid var(--p-red-500);
  border-radius: var(--p-content-border-radius);
  padding: var(--space-2) var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.lot-card--kept {
  border-left-color: var(--p-primary-color);
}

.lot-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.lot-number {
  font-weight: 600;
}

.lot-meta,
.keep-reason {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.impact-list {
  list-style: none;
  margin: 0;
  padding: 0 0 0 var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.impact-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}

.impact-row--kept {
  color: var(--p-text-muted-color);
}
</style>
