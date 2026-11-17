<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import { useRemoteOptions } from '@/shared/composables/useRemoteOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { sourceItemsApi } from '../api/sourceItemsApi'

import type { SourceItemResponse } from '../types/sourceItemsResponse'
import { catalogueStatusTagSeverity } from '@/shared/utils/catalogueStatus'
import { localizeLabel } from '@/shared/utils/localizeLabel'

interface Props {
  excludeId?: number
  placeholder?: string
  disabled?: boolean
}

const props = defineProps<Props>()

// Single-rooted with attrs forwarded explicitly, so a parent's fluid and
// v-tooltip still reach the Select next to the archived warning.
defineOptions({ inheritAttrs: false })

const model = defineModel<SourceItemResponse | null>({ default: null })

const { t } = useI18n()

const { items, loading, debouncedSearch } = useRemoteOptions(
  async (query: string): Promise<SourceItemResponse[]> => {
    const result = await sourceItemsApi.list({
      limit: 20,
      include_archived: true,
      ...(query ? { search: query } : {}),
    })
    return props.excludeId
      ? result.items.filter((item) => item.id !== props.excludeId)
      : result.items
  },
  // Keeps the selected item in the options when a search does not return it.
  { keepSelected: model },
)

// Archived source items stay selectable, sorted last.
const { sortedOptions: options, isArchived } = useArchivableOptions(items)

function itemLabel(item: SourceItemResponse): string {
  return item.dimension || `Source item #${item.id}`
}

function itemSublabel(item: SourceItemResponse): string {
  return [
    item.material,
    localizeLabel(item.type_name),
    item.mass,
    item.manufacturer_name,
    item.order_code_1,
    item.order_code_2,
  ]
    .filter(Boolean)
    .join(' | ')
}
</script>

<template>
  <div>
    <!-- eslint-disable-next-line vuejs-accessibility/form-control-has-label -- the caller labels it, aria-labelledby falls through to the Select -->
    <Select
      v-bind="$attrs"
      v-model="model"
      :options="options"
      :filter="true"
      data-key="id"
      :loading="loading"
      :placeholder="props.placeholder ?? t('sourceItems.select.placeholder')"
      :disabled="props.disabled"
      @filter="(e) => debouncedSearch(e.value)"
    >
      <template #option="{ option }">
        <div class="item-option-row">
          <div class="item-option">
            <span class="item-name">
              {{ itemLabel(option) }}
              <Tag
                :value="t(`sourceItems.catalogue.status.${option.status}`)"
                :severity="catalogueStatusTagSeverity(option.status)"
              />
              <ArchivedOptionTag v-if="option.archived" />
            </span>
            <span v-if="itemSublabel(option)" class="item-code">{{ itemSublabel(option) }}</span>
          </div>
        </div>
      </template>
      <template #value="{ value }">
        <div v-if="value" class="item-value-row">
          <span>{{ itemLabel(value) }}</span>
          <ArchivedOptionTag v-if="value.archived" />
        </div>
      </template>
    </Select>
    <ArchivedSelectionWarning v-if="isArchived(model)" />
  </div>
</template>

<style scoped lang="scss">
.item-option-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.item-option {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.item-name {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-weight: 600;
  font-size: var(--font-size-sm);
}

.item-code {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.item-value-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
