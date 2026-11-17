<script setup lang="ts">
import { useId } from 'vue'
import { useI18n } from 'vue-i18n'

import type { DemandUnitOption } from '@/shared/composables/useDemandUnitOptions'
import { quantityFractionDigits } from '@/shared/utils/units'

/**
 * The quantity/unit/items_per_unit/desired_delivery_date/high_priority/
 * notify_on_delivery/note field block shared by the bought and made-item
 * demand create forms. Renders as a flat list of `.field` divs (no
 * wrapping element) so the caller's own `.form-grid` still lays them out
 * alongside its item/project fields; a family with extra fields (made
 * items' alteration pair) renders them through the `extra-fields` slot, in
 * the same position they held in the original inline markup.
 *
 * The source-item create dialog (`features/production`) shares the same
 * fields but not this block; its `FormField`-wrapped, aria-required
 * markup is a genuinely different template, not a copy of this one.
 */

const quantity = defineModel<number | null>('quantity', { required: true })
const unit = defineModel<string>('unit', { required: true })
const itemsPerUnit = defineModel<number>('itemsPerUnit', { required: true })
const highPriority = defineModel<boolean>('highPriority', { required: true })
const notifyOnDelivery = defineModel<boolean>('notifyOnDelivery', { required: true })
const desiredDeliveryDate = defineModel<Date | null>('desiredDeliveryDate', { required: true })
const note = defineModel<string>('note', { required: true })

defineProps<{
  unitOptions: DemandUnitOption[]
  /**
   * Dot-path prefix for this block's i18n keys, e.g.
   * `boughtItems.demands.create`: each key is read as `${i18nPrefix}.fields.<name>`.
   */
  i18nPrefix: string
  /** Prefix for the checkbox input ids, unique per dialog instance on the page. */
  idPrefix: string
}>()

const emit = defineEmits<{
  /**
   * Fired only on a genuine user edit of the date picker, so the caller
   * can tell it apart from a value set programmatically (e.g. derived from
   * the selected project) and keep its own "user touched the date" flag.
   */
  dateTouched: []
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
</script>

<template>
  <div class="field">
    <label :for="`${uid}-quantity`">{{ t(`${i18nPrefix}.fields.quantity`) }} *</label>
    <InputNumber
      v-model="quantity"
      :input-id="`${uid}-quantity`"
      :min="quantityFractionDigits(unit) === 0 ? 1 : 0.001"
      :max-fraction-digits="quantityFractionDigits(unit)"
      fluid
    />
  </div>

  <div class="field">
    <label :id="`${uid}-unit-label`" :for="`${uid}-unit`">{{ t(`${i18nPrefix}.fields.unit`) }} *</label>
    <Select
      v-model="unit"
      :input-id="`${uid}-unit`"
      :aria-labelledby="`${uid}-unit-label`"
      :options="unitOptions"
      option-label="label"
      option-value="value"
      fluid
    />
  </div>

  <div class="field">
    <label :for="`${uid}-items-per-unit`">{{ t(`${i18nPrefix}.fields.itemsPerUnit`) }}</label>
    <InputNumber
      v-model="itemsPerUnit"
      :input-id="`${uid}-items-per-unit`"
      :min="0.001"
      :max-fraction-digits="3"
      fluid
    />
  </div>

  <div class="field">
    <label :for="`${uid}-desired-delivery-date`">{{ t(`${i18nPrefix}.fields.desiredDeliveryDate`) }}</label>
    <DatePicker
      v-model="desiredDeliveryDate"
      :input-id="`${uid}-desired-delivery-date`"
      show-button-bar
      show-clear
      fluid
      @update:model-value="emit('dateTouched')"
    />
  </div>

  <div class="field checkbox-field">
    <Checkbox v-model="highPriority" :input-id="`${idPrefix}-high-priority`" :binary="true" />
    <label :for="`${idPrefix}-high-priority`">{{ t(`${i18nPrefix}.fields.highPriority`) }}</label>
  </div>

  <div class="field checkbox-field">
    <Checkbox v-model="notifyOnDelivery" :input-id="`${idPrefix}-notify`" :binary="true" />
    <label :for="`${idPrefix}-notify`">{{ t(`${i18nPrefix}.fields.notifyOnDelivery`) }}</label>
  </div>

  <slot name="extra-fields" />

  <div class="field field-wide">
    <label :for="`${uid}-note`">{{ t(`${i18nPrefix}.fields.note`) }}</label>
    <Textarea v-model="note" :id="`${uid}-note`" rows="3" auto-resize fluid />
  </div>
</template>

<style scoped lang="scss">
.field-wide {
  grid-column: 1 / -1;
}

.checkbox-field {
  flex-direction: row;
  align-items: center;
  gap: var(--space-2);
}
</style>
