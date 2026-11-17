<script setup lang="ts">
/**
 * OpenVue `MultiSelect` backed by a server-side search, for table column
 * filters that pick entities (orders, lots) out of a list too long to load
 * whole. The caller passes `fetch`, which turns a search string into
 * `LookupOption`s and owns the page size, so this component has no API
 * dependency of its own and can live in `shared`.
 *
 * The option list is the latest fetched page plus every currently selected
 * entry, remembered in a local map by id, so narrowing the search never
 * drops a chip the user already picked. The search itself is
 * useLookupSearch, shared with LookupSelect.
 *
 * A selection the component did not make itself (restored store state, a
 * deep link) has no option to label its chips with, so `fetchByIds`, when
 * given, resolves any selected id the component has never seen.
 *
 * It is small by default, as a table filter; a form field passes
 * `:compact="false"` to match the inputs beside it.
 */
import { computed, ref, watch } from 'vue'

import { useLookupSearch } from './useLookupSearch'

import type { LookupFetch, LookupFetchByIds, LookupOption } from './lookupMultiSelect'

const props = withDefaults(
  defineProps<{
    modelValue: number[]
    fetch: LookupFetch
    fetchByIds?: LookupFetchByIds
    placeholder?: string
    compact?: boolean
  }>(),
  { compact: true, fetchByIds: undefined, placeholder: undefined },
)

const emit = defineEmits<{
  'update:modelValue': [value: number[]]
}>()

const selected = ref(new Map<number, LookupOption>())
const { fetched, loading, onFilter, onHide } = useLookupSearch((query) => props.fetch(query))

const options = computed<LookupOption[]>(() => {
  const fetchedIds = new Set(fetched.value.map((option) => option.id))
  const pinned: LookupOption[] = []
  for (const id of props.modelValue) {
    const option = selected.value.get(id)
    if (option && !fetchedIds.has(id)) pinned.push(option)
  }
  return [...pinned, ...fetched.value]
})

function onUpdate(value: number[] | null): void {
  const next = value ?? []
  const known = new Map(options.value.map((option) => [option.id, option]))
  const nextSelected = new Map<number, LookupOption>()
  for (const id of next) {
    const option = known.get(id) ?? selected.value.get(id)
    if (option) nextSelected.set(id, option)
  }
  selected.value = nextSelected
  emit('update:modelValue', next)
}

// Ids currently being resolved through fetchByIds, so a model that changes
// while a lookup is in flight does not request the same ids twice.
const resolving = new Set<number>()

async function resolveUnknownIds(ids: number[]): Promise<void> {
  const fetchByIds = props.fetchByIds
  if (!fetchByIds) return
  const known = new Set(options.value.map((option) => option.id))
  const missing = ids.filter((id) => !known.has(id) && !resolving.has(id))
  if (missing.length === 0) return
  for (const id of missing) resolving.add(id)
  try {
    const result = await fetchByIds(missing)
    const next = new Map(selected.value)
    for (const option of result) next.set(option.id, option)
    selected.value = next
  } finally {
    for (const id of missing) resolving.delete(id)
  }
}

watch(() => props.modelValue, resolveUnknownIds, { immediate: true })
</script>

<template>
  <MultiSelect
    :model-value="modelValue"
    :options="options"
    option-label="label"
    option-value="id"
    data-key="id"
    :loading="loading"
    filter
    :filter-fields="['label', 'sublabel']"
    reset-filter-on-hide
    display="chip"
    show-clear
    :size="compact ? 'small' : undefined"
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
  </MultiSelect>
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
