<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import type { SequenceVariantValue } from '../../types/sequence'
import { useSequenceEditor } from '../../composables/sequenceEditorContext'

/**
 * A number that may differ per product variant: one common value, and when
 * opened a value of its own for each variant, which falls back to the
 * common one while empty. Read-only, the values read as text, the common
 * one first and then each variant's own.
 */
const props = defineProps<{ unit?: string | null; inputId?: string; min?: number; placeholder?: string }>()

const model = defineModel<SequenceVariantValue | null>({ default: null })

const { t } = useI18n()
const { names, readonly } = useSequenceEditor()

const perVariant = computed(() => model.value?.per_variant ?? {})
const hasOwn = computed(() => Object.keys(perVariant.value).length > 0)
const open = ref(false)
const showVariants = computed(() => (open.value || hasOwn.value) && names.liveVariants.value.length > 0)
const ownValues = computed(() => Object.entries(perVariant.value))

function withUnit(value: number): string {
  return props.unit ? `${value} ${props.unit}` : String(value)
}

function emitValue(common: number | null, own: Record<string, number>): void {
  model.value = common === null && Object.keys(own).length === 0 ? null : { common, per_variant: own }
}

function setCommon(value: number | null): void {
  emitValue(value, { ...perVariant.value })
}

function setVariant(id: number, value: number | null): void {
  const own = { ...perVariant.value }
  if (value === null) delete own[String(id)]
  else own[String(id)] = value
  emitValue(model.value?.common ?? null, own)
}
</script>

<template>
  <span v-if="readonly" class="variant-value-text" data-testid="sequence-value-text">
    <span v-if="model?.common != null">{{ withUnit(model.common) }}</span>
    <span v-for="[id, value] in ownValues" :key="id" class="variant-own">
      {{ names.variantName(Number(id)) }} {{ withUnit(value) }}
    </span>
    <span v-if="model?.common == null && ownValues.length === 0" class="muted">{{ getEmptyPlaceholder() }}</span>
  </span>
  <div v-else class="variant-value">
    <div class="common-row">
      <InputNumber
        :model-value="model?.common ?? null"
        :input-id="inputId"
        :min="min"
        :max-fraction-digits="3"
        :placeholder="hasOwn ? t('sequences.editor.perVariant') : (placeholder ?? '')"
        :suffix="unit ? ` ${unit}` : undefined"
        size="small"
        fluid
        @update:model-value="setCommon"
      />
      <Button
        v-if="names.liveVariants.value.length > 0 && !hasOwn"
        v-tooltip.bottom="t('sequences.editor.valuesPerVariant')"
        :aria-label="t('sequences.editor.valuesPerVariant')"
        icon="mdi mdi-format-list-numbered"
        severity="secondary"
        :text="!open"
        size="small"
        @click="open = !open"
      />
    </div>
    <div v-if="showVariants" class="variants">
      <div v-for="variant in names.liveVariants.value" :key="variant.id" class="variant-row">
        <span class="variant-name">{{ variant.name }}</span>
        <InputNumber
          :model-value="perVariant[String(variant.id)] ?? null"
          :min="min"
          :max-fraction-digits="3"
          :placeholder="model?.common != null ? String(model.common) : ''"
          :suffix="unit ? ` ${unit}` : undefined"
          :aria-label="variant.name"
          size="small"
          fluid
          @update:model-value="(value: number | null) => setVariant(variant.id, value)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.variant-value-text {
  display: inline-flex;
  gap: var(--space-2);
  align-items: baseline;
  flex-wrap: wrap;
}

.variant-own {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.muted {
  color: var(--p-text-muted-color);
}

.variant-value {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 8rem;
}

.common-row {
  display: flex;
  gap: var(--space-1);
  align-items: center;
}

.variants {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-left: var(--space-2);
  border-left: 2px solid var(--p-content-border-color);
}

.variant-row {
  display: grid;
  grid-template-columns: minmax(5rem, auto) 1fr;
  gap: var(--space-2);
  align-items: center;
}

.variant-name {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
