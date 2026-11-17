<script setup lang="ts">
// Picks the catalogue item a quote request line takes instead of its own,
// searched remotely in the catalogue of the line's kind.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useRemoteOptions } from '@/shared/composables/useRemoteOptions'
import { searchSubstituteItems } from '../api/searchSubstituteItems'
import type { SubstituteItemOption } from '../api/searchSubstituteItems'

const props = defineProps<{
  kind: 'BOUGHT' | 'SOURCE'
  /** The line's own item, which is no substitute. */
  excludeId: number | null
  inputId?: string
  disabled?: boolean
}>()

const model = defineModel<SubstituteItemOption | null>({ default: null })

const { t } = useI18n()

const { items, loading, debouncedSearch } = useRemoteOptions((query: string) =>
  searchSubstituteItems(props.kind, query),
)

// The chosen item stays an option while a search shows other items.
const options = computed(() => {
  const found = items.value.filter((item) => item.id !== props.excludeId)
  const chosen = model.value
  return chosen && !found.some((item) => item.id === chosen.id) ? [chosen, ...found] : found
})

// The template root is a single element, so a disable comment in front
// of it would turn the root into a fragment and stop attribute fallthrough.
/* eslint-disable vuejs-accessibility/form-control-has-label -- the caller labels it, aria-labelledby falls through to the Select */
</script>

<template>
  <Select
    v-model="model"
    :options="options"
    option-label="name"
    data-key="id"
    filter
    :filter-fields="['name', 'code']"
    :loading="loading"
    :disabled="props.disabled"
    :input-id="props.inputId"
    :placeholder="t('quoteRequests.substitute.itemPlaceholder')"
    fluid
    @filter="(e) => debouncedSearch(e.value)"
  >
    <template #option="{ option }: { option: SubstituteItemOption }">
      <div class="item-option">
        <span class="item-name">{{ option.name }}</span>
        <span v-if="option.code" class="item-code">{{ option.code }}</span>
      </div>
    </template>
    <template #value="{ value }: { value: SubstituteItemOption | null }">
      <span v-if="value">{{ value.name }}<span v-if="value.code" class="item-code"> · {{ value.code }}</span></span>
      <span v-else class="item-code">{{ t('quoteRequests.substitute.itemPlaceholder') }}</span>
    </template>
  </Select>
</template>

<style scoped lang="scss">
.item-option {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.item-name {
  font-weight: 600;
  font-size: var(--font-size-sm);
}

.item-code {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
