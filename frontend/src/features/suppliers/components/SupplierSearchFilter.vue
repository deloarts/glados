<script setup lang="ts">
import { ref, watch } from 'vue'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import { getSuppliers } from '@/features/suppliers/api/getSuppliers'
import type { SupplierResponse } from '@/features/suppliers/types/supplierResponse'

const props = defineProps<{
  modelValue: number | null
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number | null]
}>()

const inputValue = ref<SupplierResponse | null>(null)
const suggestions = ref<SupplierResponse[]>([])

// Archived suppliers stay findable, sorted last.
const { sortedOptions: suggestionOptions } = useArchivableOptions(suggestions)

watch(
  () => props.modelValue,
  (id) => {
    if (id === null) inputValue.value = null
  },
)

async function onComplete(event: { query: string }): Promise<void> {
  try {
    const result = await getSuppliers({ name: event.query, limit: 30, include_archived: true })
    suggestions.value = result.items
  } catch {
    suggestions.value = []
  }
}

function onSelect(event: { value: SupplierResponse }): void {
  emit('update:modelValue', event.value.id)
}

function onClear(): void {
  emit('update:modelValue', null)
}
</script>

<template>
  <AutoComplete
    v-model="inputValue"
    :suggestions="suggestionOptions"
    option-label="name"
    @complete="onComplete"
    @option-select="onSelect"
    @clear="onClear"
    show-clear
    force-selection
    :placeholder="placeholder"
    size="small"
    fluid
  >
    <template #option="{ option }">
      <span>{{ option.name }}</span>
      <ArchivedOptionTag v-if="option.archived" />
    </template>
  </AutoComplete>
</template>
