<script setup lang="ts">
// Quantity and unit inputs of an order item row in edit mode. The quantity
// is locked once the line is no longer open, since a line that received
// pieces is closed short instead of shrunk, and the unit once it received
// goods, since that would rewrite what arrived.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { BOUGHT_ITEM_UNIT_CODES, quantityFractionDigits } from '@/shared/utils/units'


const quantity = defineModel<number>('quantity', { required: true })
const unit = defineModel<string>('unit', { required: true })

defineProps<{
  quantityLocked?: boolean
  unitLocked?: boolean
}>()

const { t } = useI18n()

const unitOptions = computed(() =>
  BOUGHT_ITEM_UNIT_CODES.map((code) => ({ value: code, label: t(`boughtItems.units.${code}`) })),
)
</script>

<template>
  <div class="edit-qty-unit">
    <InputNumber
      v-model="quantity"
      :disabled="quantityLocked"
      :min="quantityFractionDigits(unit) === 0 ? 1 : 0.001"
      :max-fraction-digits="quantityFractionDigits(unit)"
      :input-style="{ width: '5rem' }"
      size="small"
    />
    <Select
      v-model="unit"
      :aria-label="t('orders.items.columns.unit')"
      :options="unitOptions"
      :disabled="unitLocked"
      option-label="label"
      option-value="value"
      size="small"
      style="min-width: 9rem"
    />
  </div>
</template>

<style scoped lang="scss">
.edit-qty-unit {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
