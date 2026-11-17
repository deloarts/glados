<script setup lang="ts">
/**
 * The single-choice sibling of LookupMultiSelect: an OpenVue `Select` backed
 * by a server-side search, for a column filter that picks one entity (a
 * project, a manufacturer) out of a list too long to load whole. The first
 * page loads when the filter mounts, typing narrows it on the server, and
 * the caller's `fetch` owns the page size.
 *
 * The chosen entry stays an option while a search shows others. A choice
 * the component did not make itself (restored store state) is labelled
 * through `fetchByIds` when given. It is small, as a filter in a table
 * header is, unless `size` is `normal`, which matches the other fields of
 * a form.
 */
import { computed, ref, watch } from 'vue'

import { useLookupSearch } from './useLookupSearch'

import type { LookupFetch, LookupFetchByIds, LookupOption } from './lookupMultiSelect'

const props = withDefaults(
  defineProps<{
    modelValue: number | null
    fetch: LookupFetch
    fetchByIds?: LookupFetchByIds
    placeholder?: string
    size?: 'small' | 'normal'
  }>(),
  { fetchByIds: undefined, placeholder: undefined, size: 'small' },
)

const emit = defineEmits<{
  'update:modelValue': [value: number | null]
}>()

const selected = ref<LookupOption | null>(null)
const { fetched, loading, onFilter, onHide } = useLookupSearch((query) => props.fetch(query))

const options = computed<LookupOption[]>(() => {
  const chosen = selected.value
  if (!chosen || chosen.id !== props.modelValue) return fetched.value
  return fetched.value.some((option) => option.id === chosen.id)
    ? fetched.value
    : [chosen, ...fetched.value]
})

function onUpdate(value: number | null): void {
  selected.value = value === null ? null : (options.value.find((o) => o.id === value) ?? null)
  emit('update:modelValue', value)
}

async function resolveUnknownId(id: number | null): Promise<void> {
  if (id === null) {
    selected.value = null
    return
  }
  if (!props.fetchByIds || options.value.some((option) => option.id === id)) return
  const [found] = await props.fetchByIds([id])
  if (found && props.modelValue === id) selected.value = found
}

watch(() => props.modelValue, resolveUnknownId, { immediate: true })

// The template root is a single element, so a disable comment in front
// of it would turn the root into a fragment and stop attribute fallthrough.
/* eslint-disable vuejs-accessibility/form-control-has-label -- the caller labels it, aria-labelledby falls through to the Select */
</script>

<template>
  <Select
    :model-value="modelValue"
    :options="options"
    option-label="label"
    option-value="id"
    data-key="id"
    :loading="loading"
    filter
    :filter-fields="['label', 'sublabel']"
    reset-filter-on-hide
    show-clear
    :size="size === 'small' ? 'small' : undefined"
    fluid
    :placeholder="placeholder"
    @update:model-value="onUpdate"
    @filter="(e) => onFilter(e.value)"
    @hide="onHide"
  >
    <template #option="{ option }">
      <div class="lookup-option">
        <span class="lookup-label">{{ option.label }}</span>
        <span v-if="option.sublabel" class="lookup-sublabel">{{ option.sublabel }}</span>
      </div>
    </template>
  </Select>
</template>

<style scoped lang="scss">
.lookup-option {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.lookup-label {
  font-size: var(--font-size-sm);
}

.lookup-sublabel {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
