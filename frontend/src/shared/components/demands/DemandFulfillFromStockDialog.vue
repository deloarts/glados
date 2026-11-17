<script
  setup
  lang="ts"
  generic="
    TDemand extends FulfillFromStockDemand,
    TSummary extends FulfillFromStockSummary,
    TResult extends FulfillFromStockResult
  "
>
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'

/**
 * The demand fields this dialog reads. `item_article_name` is optional
 * because not every demand kind carries it on the same shape (source-item
 * demands name their linked bought/source item on separate fields instead),
 * in which case the dialog header simply omits the item name suffix.
 */
export interface FulfillFromStockDemand {
  id: number
  unit: string
  item_article_name?: string
}

export interface FulfillFromStockSummary {
  unallocated: number
  unit: string
}

export interface FulfillFromStockResult {
  quantity_fulfilled: number
}

/**
 * The 3 allocation-store members this dialog calls, kept as their own
 * interface so any feature's allocations store (or a plain object wrapping
 * one) can be passed through without this component importing a concrete
 * store type from a feature.
 */
export interface FulfillFromStockOperations<TSummary, TResult> {
  getSummary: (demandId: number) => TSummary | undefined
  fetchSummaries: (demandIds: number[]) => Promise<void>
  fulfillFromStock: (demandId: number, quantity: number) => Promise<TResult>
}

const props = defineProps<{
  demand: TDemand | null
  operations: FulfillFromStockOperations<TSummary, TResult>
  /**
   * Dot-path prefix shared by every i18n key this dialog reads, e.g.
   * `boughtItems.demands`: the suffixes (`fulfillFromStockDialog.title`,
   * `detail.fulfillFromStock`, and so on) are identical across item kinds.
   */
  i18nPrefix: string
  /**
   * Locale-aware short label for a unit code. Feature-owned (bought-items
   * defines the unit list), so it is passed in rather than imported here.
   */
  formatUnit: (unit: string) => string
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  fulfilled: []
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()

const quantity = ref<number | null>(null)
const submitting = ref(false)
const successMessage = ref<string | null>(null)
const errorMessage = ref<string | null>(null)

const summary = computed(() =>
  props.demand ? props.operations.getSummary(props.demand.id) : undefined,
)

const header = computed(() => {
  const title = t(`${props.i18nPrefix}.fulfillFromStockDialog.title`)
  const itemName = props.demand?.item_article_name
  return itemName ? `${title}, ${itemName}` : title
})

watch(visible, async (open) => {
  if (!open || !props.demand) return

  quantity.value = null
  successMessage.value = null
  errorMessage.value = null

  if (!summary.value) {
    await props.operations.fetchSummaries([props.demand.id])
  }
  // Covering the whole open quantity is the usual case, so it is prefilled;
  // the user lowers it for a partial cover.
  const openQuantity = summary.value?.unallocated ?? 0
  if (visible.value && quantity.value === null && openQuantity > 0) quantity.value = openQuantity
})

const canSubmit = computed(
  () =>
    !!quantity.value &&
    quantity.value > 0 &&
    (!summary.value || quantity.value <= summary.value.unallocated),
)

async function onSubmit(): Promise<void> {
  if (!props.demand || !quantity.value) return

  submitting.value = true
  errorMessage.value = null

  try {
    const result = await props.operations.fulfillFromStock(props.demand.id, quantity.value)
    successMessage.value = t(`${props.i18nPrefix}.detail.fulfillFromStockSuccess`, {
      quantity: result.quantity_fulfilled,
      unit: summary.value?.unit ?? props.demand.unit,
    })
    quantity.value = null
    emit('fulfilled')
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t(`${props.i18nPrefix}.detail.errors.unknown`)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :header="header" :style="{ width: 'var(--dialog-width-sm)' }">
    <div v-if="demand" class="fulfill-form">
      <div class="field">
        <label :for="`${uid}-quantity`">{{ t(`${i18nPrefix}.detail.fulfillFromStock`) }}</label>
        <InputNumber
          v-model="quantity"
          :input-id="`${uid}-quantity`"
          :min="0.001"
          :max="summary?.unallocated ?? undefined"
          :max-fraction-digits="3"
          :placeholder="t(`${i18nPrefix}.detail.fulfillFromStockPlaceholder`)"
          fluid
        />
        <span v-if="summary" class="hint">
          {{ t(`${i18nPrefix}.detail.unallocated`) }}: {{ summary.unallocated }}
          {{ formatUnit(summary.unit) }}
        </span>
      </div>

      <Message v-if="successMessage" severity="success" :closable="false">{{
        successMessage
      }}</Message>
      <Message v-if="errorMessage" severity="error" :closable="false">{{ errorMessage }}</Message>
    </div>

    <template #footer>
      <Button :label="t('common.close')" severity="secondary" outlined @click="visible = false" />
      <Button
        :label="t(`${i18nPrefix}.detail.fulfillFromStock`)"
        :loading="submitting"
        :disabled="!canSubmit"
        @click="onSubmit"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.fulfill-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
</style>
