<script setup lang="ts">
// Edits a list of extra costs (shipping, packaging, surcharges, a discount)
// in place. Orders and the offers of a quote request share it; the caller
// saves the list as a whole. Amounts are entered in the currency and held
// in cents.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { currencyInputPrefix, formatPrice } from '@/core/utils/currency'
import { EXTRA_COST_KINDS, extraCostNeedsLabel, signedExtraCost } from '@/shared/utils/extraCosts'
import type { ExtraCostDraft } from '@/shared/utils/extraCosts'

export interface ExtraCostLineOption {
  value: number
  label: string
}

const props = withDefaults(
  defineProps<{
    /** The lines a cost may belong to; without any the line column is left out. */
    lineOptions?: ExtraCostLineOption[]
    /** What a cost of no line belongs to, such as the whole order. */
    wholeLabel?: string
    disabled?: boolean
  }>(),
  { lineOptions: () => [], wholeLabel: undefined, disabled: false },
)

const drafts = defineModel<ExtraCostDraft[]>({ required: true })

const { t } = useI18n()

const kindOptions = computed(() =>
  EXTRA_COST_KINDS.map((kind) => ({ value: kind, label: t(`common.extraCosts.kinds.${kind}`) })),
)

const total = computed(() =>
  drafts.value.reduce(
    (sum, draft) => sum + (draft.amount === null ? 0 : signedExtraCost(draft.kind, draft.amount)),
    0,
  ),
)

// The input works in the currency, the draft holds cents.
function amountOf(draft: ExtraCostDraft): number | null {
  return draft.amount === null ? null : draft.amount / 100
}

function setAmount(draft: ExtraCostDraft, value: number | null): void {
  draft.amount = value === null ? null : Math.round(value * 100)
}

function addCost(): void {
  drafts.value = [
    ...drafts.value,
    { kind: 'shipping', amount: null, label: '', note: '', lineId: null },
  ]
}

function removeCost(index: number): void {
  drafts.value = drafts.value.filter((_, i) => i !== index)
}
</script>

<template>
  <div class="extra-costs-editor">
    <div v-if="drafts.length === 0" class="empty-hint">{{ t('common.extraCosts.empty') }}</div>

    <div
      v-for="(draft, index) in drafts"
      :key="index"
      class="cost-row"
      :class="{ 'with-line': props.lineOptions.length > 0 }"
      data-testid="extra-cost-row"
    >
      <div class="field">
        <label :id="`extra-cost-kind-${index}-label`" :for="`extra-cost-kind-${index}`">{{ t('common.extraCosts.fields.kind') }}</label>
        <Select
          v-model="draft.kind"
          :input-id="`extra-cost-kind-${index}`"
          :aria-labelledby="`extra-cost-kind-${index}-label`"
          :options="kindOptions"
          option-label="label"
          option-value="value"
          :disabled="props.disabled"
          fluid
        />
      </div>
      <div class="field">
        <label :for="`extra-cost-amount-${index}`">
          {{ t('common.extraCosts.fields.amount') }} *
        </label>
        <InputNumber
          :model-value="amountOf(draft)"
          :input-id="`extra-cost-amount-${index}`"
          :min="0.01"
          :min-fraction-digits="2"
          :max-fraction-digits="2"
          :prefix="currencyInputPrefix()"
          :disabled="props.disabled"
          fluid
          @update:model-value="setAmount(draft, $event)"
        />
      </div>
      <div class="field">
        <label :for="`extra-cost-label-${index}`">
          {{ t('common.extraCosts.fields.label') }}{{ extraCostNeedsLabel(draft.kind) ? ' *' : '' }}
        </label>
        <InputText
          v-model="draft.label"
          :id="`extra-cost-label-${index}`"
          :maxlength="120"
          :disabled="props.disabled"
          fluid
        />
      </div>
      <div v-if="props.lineOptions.length > 0" class="field">
        <label :id="`extra-cost-line-${index}-label`" :for="`extra-cost-line-${index}`">{{ t('common.extraCosts.fields.line') }}</label>
        <Select
          v-model="draft.lineId"
          :input-id="`extra-cost-line-${index}`"
          :aria-labelledby="`extra-cost-line-${index}-label`"
          :options="props.lineOptions"
          option-label="label"
          option-value="value"
          :placeholder="props.wholeLabel ?? t('common.extraCosts.wholeDocument')"
          :disabled="props.disabled"
          show-clear
          fluid
        />
      </div>
      <div class="field note-field">
        <label :for="`extra-cost-note-${index}`">{{ t('common.extraCosts.fields.note') }}</label>
        <InputText
          v-model="draft.note"
          :id="`extra-cost-note-${index}`"
          :disabled="props.disabled"
          fluid
        />
      </div>
      <Button
        class="remove-button"
        icon="mdi mdi-delete-outline"
        severity="secondary"
        text
        rounded
        :aria-label="t('common.extraCosts.remove')"
        v-tooltip.top="t('common.extraCosts.remove')"
        :disabled="props.disabled"
        @click="removeCost(index)"
      />
    </div>

    <div class="editor-footer">
      <Button
        icon="mdi mdi-plus"
        :label="t('common.extraCosts.add')"
        severity="contrast"
        text
        :disabled="props.disabled"
        @click="addCost"
      />
      <span class="total">
        {{ t('common.extraCosts.total') }}: <strong>{{ formatPrice(total) }}</strong>
      </span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.extra-costs-editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.empty-hint {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.cost-row {
  display: grid;
  grid-template-columns: 11rem 8rem 1fr 1fr auto;
  gap: var(--space-2);
  align-items: end;
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--p-content-border-color);

  &.with-line {
    grid-template-columns: 11rem 8rem 1fr 12rem 1fr auto;
  }
}

.field {
  min-width: 0;

  label {
    font-size: var(--font-size-sm);
  }
}

.editor-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.total {
  font-size: var(--font-size-sm);
}

@media (max-width: $bp-md) {
  .cost-row,
  .cost-row.with-line {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
