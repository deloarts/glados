<script lang="ts">
// Module-level so part row ids stay stable across mounts and keep each
// row's input tied to it when a sibling is removed.
let nextPartRowId = 0

function createPartRowId(): number {
  return ++nextPartRowId
}
</script>

<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { HelpDrawer } from '@/shared/help'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { useProductionQueueStore } from '../../stores/productionQueueStore'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'

const props = defineProps<{
  order: ProductionOrderResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const explainVisible = ref(false)
// Prefixes the ids that tie each label to its control.
const uid = useId()
const store = useProductionQueueStore()

// Same tolerance as the backend's split sum check.
const QUANTITY_EPSILON = 1e-6

interface PartRow {
  id: number
  quantity: number | null
}

function createRowsFor(order: ProductionOrderResponse | null): PartRow[] {
  if (!order) return [{ id: createPartRowId(), quantity: null }, { id: createPartRowId(), quantity: null }]
  // Whole pieces: an odd quantity puts the extra piece in the second part.
  const half = Math.floor(order.quantity / 2)
  return [
    { id: createPartRowId(), quantity: half },
    { id: createPartRowId(), quantity: order.quantity - half },
  ]
}

const rows = ref<PartRow[]>(createRowsFor(props.order))
const { submitting, errorMessage, run } = useSubmitAction()

watch(visible, (isVisible) => {
  if (!isVisible) return
  rows.value = createRowsFor(props.order)
  errorMessage.value = null
})

function addPart(): void {
  rows.value.push({ id: createPartRowId(), quantity: null })
}

function removePart(id: number): void {
  if (rows.value.length <= 2) return
  rows.value = rows.value.filter((row) => row.id !== id)
}

const quantities = computed(() => rows.value.map((row) => row.quantity))

const sum = computed(() => quantities.value.reduce((total: number, q) => total + (q ?? 0), 0))

const sumMatches = computed(() => {
  if (!props.order) return false
  return Math.abs(sum.value - props.order.quantity) <= QUANTITY_EPSILON
})

const isValid = computed(() => {
  if (rows.value.length < 2) return false
  if (quantities.value.some((q) => q === null || q <= 0)) return false
  return sumMatches.value
})

async function onSubmit(): Promise<void> {
  const order = props.order
  if (!order || !isValid.value) {
    errorMessage.value = t('productionQueue.split.errors.invalid')
    return
  }

  await run(async () => {
    await store.split(order.id, { quantities: quantities.value as number[] })
    visible.value = false
  }, t('productionQueue.split.errors.unknown'))
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: 'var(--dialog-width-md)' }">
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ t('productionQueue.split.title') }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('productionQueue.split.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('productionQueue.split.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>

    <div v-if="order" class="split-form">
      <p class="description">
        {{ t('productionQueue.split.description', { quantity: order.quantity }) }}
      </p>

      <div v-for="(row, index) in rows" :key="row.id" class="part-row">
        <label :for="`${uid}-part-${row.id}`" class="part-label">{{
          t('productionQueue.split.part', { index: index + 1 })
        }}</label>
        <InputNumber
          v-model="row.quantity"
          :input-id="`${uid}-part-${row.id}`"
          :min="1"
          :max-fraction-digits="0"
          fluid
        />
        <Button
          icon="mdi mdi-close"
          text
          rounded
          severity="danger"
          :disabled="rows.length <= 2"
          :aria-label="t('productionQueue.split.removePart')"
          @click="removePart(row.id)"
        />
      </div>

      <Button
        :label="t('productionQueue.split.addPart')"
        icon="mdi mdi-plus"
        severity="secondary"
        outlined
        size="small"
        @click="addPart"
      />

      <div class="sum-row" :class="{ mismatch: !sumMatches }">
        {{ t('productionQueue.split.sum', { sum, quantity: order.quantity }) }}
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
        :label="t('common.save')"
        :loading="submitting"
        :disabled="!isValid"
        @click="onSubmit"
      />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="production/queue" anchor="split" />
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

.split-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.description {
  margin: 0;
  color: var(--p-text-muted-color);
}

.part-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.part-label {
  min-width: 5rem;
  font-size: var(--font-size-sm);
}

.sum-row {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);

  &.mismatch {
    color: var(--p-red-500);
    font-weight: 600;
  }
}
</style>
