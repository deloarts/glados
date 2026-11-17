<script setup lang="ts">
import { useRemoteOptions } from '@/shared/composables/useRemoteOptions'
import { searchProjects } from '@/core/api/projects/searchProjects'
import type { ProjectRef } from '@/core/types/projectRef'

interface Props {
  inputId?: string
  disabled?: boolean
}

defineProps<Props>()

const model = defineModel<ProjectRef | null>({ default: null })

const {
  items: projectOptions,
  loading: loadingProjects,
  debouncedSearch: debouncedProjectSearch,
} = useRemoteOptions(async (query: string): Promise<ProjectRef[]> => {
  const result = await searchProjects({
    limit: 50,
    status: 'active',
    ...(query ? { project_number: query } : {}),
  })
  return result.items
})

// The template root is a single element, so a disable comment in front
// of it would turn the root into a fragment and stop attribute fallthrough.
/* eslint-disable vuejs-accessibility/form-control-has-label -- the caller labels it, aria-labelledby falls through to the Select */
</script>

<template>
  <Select
    :input-id="inputId"
    v-model="model"
    :options="projectOptions"
    :loading="loadingProjects"
    :filter-fields="['project_number']"
    :disabled="disabled"
    show-clear
    filter
    fluid
    @filter="(e) => debouncedProjectSearch(e.value)"
  >
    <template #option="{ option }">
      <div class="item-option">
        <span class="item-name">{{ option.project_number }}</span>
        <span class="item-customer">{{ option.customer?.name }} {{ option.description }}</span>
      </div>
    </template>
    <template #value="{ value }">
      <span v-if="value"
        >{{ value.project_number }} - {{ value.customer?.name }} - {{ value.description }}</span
      >
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

.item-customer {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
