<script setup lang="ts">
import { formatAddress } from '@/shared/utils/address'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import { useRemoteOptions } from '@/shared/composables/useRemoteOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { getCustomers } from '../api/getCustomers'
import type { CustomerResponse } from '../types/customerResponse'

interface Props {
  inputId?: string
  disabled?: boolean
}

// The template has two roots, so the caller's attributes, such as
// aria-labelledby, go to the Select explicitly.
defineOptions({ inheritAttrs: false })

defineProps<Props>()

const model = defineModel<CustomerResponse | null>({ default: null })

const {
  items: customers,
  loading: loadingCustomers,
  debouncedSearch: debouncedCustomerSearch,
} = useRemoteOptions(async (query: string): Promise<CustomerResponse[]> => {
  const result = await getCustomers({
    limit: 50,
    include_archived: true,
    ...(query ? { name: query } : {}),
  })
  return result.items
})

// Archived customers stay selectable, sorted last.
const { sortedOptions: customerOptions, isArchived } = useArchivableOptions(customers)

// The template root is a single element, so a disable comment in front
// of it would turn the root into a fragment and stop attribute fallthrough.
/* eslint-disable vuejs-accessibility/form-control-has-label -- the caller labels it, aria-labelledby falls through to the Select */
</script>

<template>
  <Select
    v-bind="$attrs"
    :input-id="inputId"
    v-model="model"
    :options="customerOptions"
    :loading="loadingCustomers"
    :filter-fields="['name']"
    :disabled="disabled"
    show-clear
    filter
    fluid
    @filter="(e) => debouncedCustomerSearch(e.value)"
  >
    <template #option="{ option }">
      <div class="item-option">
        <span class="item-name"
          >{{ option.name }}
          <ArchivedOptionTag v-if="option.archived" />
        </span>
        <span v-if="option.street" class="item-street">{{ option.street }}</span>
        <span v-if="option.postal_code || option.city" class="item-city">{{
          formatAddress({ postal_code: option.postal_code, city: option.city })
        }}</span>
      </div>
    </template>
    <template #value="{ value }">
      <span v-if="value"
        >{{ value.name }}<template v-if="formatAddress(value)"> - {{ formatAddress(value) }}</template>
        <ArchivedOptionTag v-if="value.archived" />
      </span>
    </template>
  </Select>
  <ArchivedSelectionWarning v-if="isArchived(model)" />
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

.item-street {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.item-city {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
