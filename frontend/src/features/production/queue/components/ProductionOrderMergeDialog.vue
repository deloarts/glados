<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { HelpDrawer } from '@/shared/help'
import { hasAction } from '@/core/utils/lifecycleActions'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { useProductionQueueStore } from '../../stores/productionQueueStore'
import { useMadeItemLabel } from '@/features/made-items'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'

const props = defineProps<{
  order: ProductionOrderResponse | null
  orders: ProductionOrderResponse[]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const explainVisible = ref(false)
const store = useProductionQueueStore()
const { format: madeItemLabel } = useMadeItemLabel()

const selectedIds = ref<number[]>([])
const { submitting, errorMessage, run } = useSubmitAction()

// Merge is only meaningful between orders that offer it, the queued ones, on
// the same machine and in the same machine pool that came from the same lot
// position (mirrors the backend's MergeProductionOrders use case, which
// requires all merged orders to share machine, pool and position).
const siblings = computed<ProductionOrderResponse[]>(() => {
  if (!props.order) return []
  return props.orders.filter(
    (o) =>
      o.id !== props.order!.id &&
      hasAction(o, 'merge') &&
      o.machine_id === props.order!.machine_id &&
      (o.machine_pool_id ?? null) === (props.order!.machine_pool_id ?? null) &&
      o.lot_position_id === props.order!.lot_position_id,
  )
})

watch(visible, (isVisible) => {
  if (!isVisible) return
  selectedIds.value = []
  errorMessage.value = null
})

const isValid = computed(() => selectedIds.value.length >= 1)

async function onSubmit(): Promise<void> {
  const order = props.order
  if (!order || !isValid.value) return

  // The edit version of every merged order as this dialog shows it, so an
  // order that changed since answers 409 instead of being merged.
  const merged = [order, ...siblings.value.filter((o) => selectedIds.value.includes(o.id))]
  await run(async () => {
    await store.merge({
      production_order_ids: merged.map((o) => o.id),
      expected_edit_versions: Object.fromEntries(merged.map((o) => [o.id, o.edit_version])),
    })
    visible.value = false
  }, t('productionQueue.merge.errors.unknown'))
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: 'var(--dialog-width-md)' }">
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ t('productionQueue.merge.title') }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('productionQueue.merge.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('productionQueue.merge.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>

    <div v-if="order" class="merge-form">
      <p class="description">{{ t('productionQueue.merge.description') }}</p>
      <p class="merge-context">
        {{ madeItemLabel(order.made_item_part_number, order.made_item_revision) }}, {{ order.lot_number }}
        <span v-if="order.lot_position_count > 1"
          >(Pos {{ order.lot_position_sequence }}/{{ order.lot_position_count }})</span
        >
      </p>

      <Message v-if="siblings.length === 0" severity="info" :closable="false">
        {{ t('productionQueue.merge.noSiblings') }}
      </Message>

      <div v-else class="sibling-list">
        <div v-for="sibling in siblings" :key="sibling.id" class="sibling-row">
          <Checkbox v-model="selectedIds" :value="sibling.id" :input-id="`sibling-${sibling.id}`" />
          <label :for="`sibling-${sibling.id}`">
            {{ sibling.production_order_number }}, {{ t('productionQueue.merge.qty', { qty: sibling.quantity }) }}
          </label>
        </div>
      </div>

      <Message v-if="errorMessage" severity="error" :closable="false">
        {{ errorMessage }}
      </Message>
    </div>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="submitting"
        @click="visible = false"
      />
      <Button
        :label="t('productionQueue.merge.submit')"
        :loading="submitting"
        :disabled="!isValid"
        @click="onSubmit"
      />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="production/queue" anchor="merge" />
</template>

<style scoped lang="scss">
.dialog-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.dialog-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.merge-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.description {
  margin: 0;
  color: var(--p-text-muted-color);
}

.merge-context {
  margin: 0;
  font-weight: 600;
  font-size: var(--font-size-sm);
}

.sibling-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sibling-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
