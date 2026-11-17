<script setup lang="ts">
// Picks a bought item's product family. Only live families are offered,
// since the backend refuses to assign an archived one; a family the item
// already has stays shown even after it was archived.
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

import { useProductFamiliesStore } from '../stores/productFamiliesStore'
import type { ProductFamilyResponse } from '../types/productFamilyResponse'

const props = defineProps<{
  inputId?: string
  disabled?: boolean
  /** Overrides the default placeholder, e.g. to say a selection holds mixed values. */
  placeholder?: string
}>()

const model = defineModel<number | null>({ default: null })

const { t } = useI18n()
const store = useProductFamiliesStore()

const options = computed<ProductFamilyResponse[]>(() =>
  store.items.filter((f) => !f.archived || f.id === model.value),
)
const selected = computed(() => store.items.find((f) => f.id === model.value) ?? null)

onMounted(() => {
  if (store.items.length === 0) void store.refresh()
})

// The template root is a single element, so a disable comment in front
// of it would turn the root into a fragment and stop attribute fallthrough.
/* eslint-disable vuejs-accessibility/form-control-has-label -- the caller labels it, aria-labelledby falls through to the Select */
</script>

<template>
  <Select
    v-model="model"
    :input-id="inputId"
    :options="options"
    option-label="name"
    option-value="id"
    :loading="store.loading"
    :placeholder="props.placeholder ?? t('settings.productFamilies.selectPlaceholder')"
    :disabled="disabled"
    filter
    show-clear
    fluid
  >
    <template #option="{ option }">
      <Tag
        :value="option.name"
        :style="{ color: option.label_font_color, backgroundColor: option.label_color }"
      />
    </template>
    <template #value="{ value, placeholder: emptyText }">
      <Tag
        v-if="value && selected"
        :value="selected.name"
        :style="{ color: selected.label_font_color, backgroundColor: selected.label_color }"
      />
      <span v-else>{{ emptyText }}</span>
    </template>
  </Select>
</template>
