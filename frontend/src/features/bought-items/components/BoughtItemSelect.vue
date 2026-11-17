<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useHostStore } from '@/core/host/stores/hostStore'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import { useRemoteOptions } from '@/shared/composables/useRemoteOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { getBoughtItems } from '../api/getBoughtItems'
import BoughtItemThumbnailCell from './BoughtItemThumbnailCell.vue'
import type { BoughtItemResponse } from '../types/boughtItemsResponse'
import { catalogueStatusTagSeverity } from '@/shared/utils/catalogueStatus'

interface Props {
  excludeId?: number
  /**
   * Replaces the catalogue search behind the options, for a caller that
   * offers its own candidates, e.g. a merge's targets.
   */
  fetchOptions?: (query: string) => Promise<BoughtItemResponse[]>
  /**
   * Why an option may not be picked, null when it may. Such an option stays
   * listed, disabled, with the reason as its tooltip.
   */
  disabledReason?: (item: BoughtItemResponse) => string | null
  disabled?: boolean
}

const props = defineProps<Props>()

// Single-rooted with attrs forwarded explicitly, so a parent's fluid and
// v-tooltip still reach the Select next to the archived warning.
defineOptions({ inheritAttrs: false })

const model = defineModel<BoughtItemResponse | null>({ default: null })

const { t } = useI18n()

const hostStore = useHostStore()

async function searchCatalogue(query: string): Promise<BoughtItemResponse[]> {
  const result = await getBoughtItems({
    limit: 50,
    include_archived: true,
    ...(query ? { search: query } : {}),
  })
  return result.items
}

const { items, loading, debouncedSearch } = useRemoteOptions((query: string) =>
  (props.fetchOptions ?? searchCatalogue)(query),
)

function refusalOf(item: BoughtItemResponse): string | null {
  return props.disabledReason?.(item) ?? null
}

const filteredItems = computed(() =>
  props.excludeId !== undefined ? items.value.filter((i) => i.id !== props.excludeId) : items.value,
)

// Archived items stay selectable, sorted last.
const { sortedOptions: options, isArchived } = useArchivableOptions(filteredItems)

</script>

<template>
  <div>
    <!-- eslint-disable-next-line vuejs-accessibility/form-control-has-label -- the caller labels it, aria-labelledby falls through to the Select -->
    <Select
      v-bind="$attrs"
      v-model="model"
      :options="options"
      :filter="true"
      :filter-fields="['order_code_1', 'article_name']"
      :loading="loading"
      :option-disabled="(option: BoughtItemResponse) => refusalOf(option) !== null"
      :disabled="props.disabled"
      @filter="(e) => debouncedSearch(e.value)"
    >
      <template #option="{ option }">
        <!-- OpenVue turns off pointer events inside a disabled option, so a
             refused row turns them back on for its tooltip and swallows the
             mousedown that would otherwise still pick it. -->
        <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- keeps a refused option from being picked, the option element itself is the Select's -->
        <div
          class="item-option-row"
          :class="{ 'item-option-refused': refusalOf(option) !== null }"
          :data-testid="refusalOf(option) !== null ? 'refused-option' : undefined"
          v-tooltip.top="refusalOf(option) ?? undefined"
          @mousedown="refusalOf(option) !== null && $event.stopPropagation()"
        >
          <BoughtItemThumbnailCell
            v-if="hostStore.storageEnabled"
            :item-id="option.id"
            :item-name="option.article_name"
            size="3.4rem"
            no-image-icon="mdi mdi-image-outline"
            style="margin-right: var(--space-2)"
          />
          <div class="item-option">
            <span class="item-name"
              >{{ option.article_name }}
              <Tag
                :value="t(`boughtItems.catalogue.status.${option.status}`)"
                :severity="catalogueStatusTagSeverity(option.status)"
              />
              <ArchivedOptionTag v-if="option.archived" />
            </span>
            <span class="item-code">{{ option.order_code_1 }}</span>
            <span class="item-manufacturer">{{ option.manufacturer_name }}</span>
          </div>
        </div>
      </template>
      <template #value="{ value }">
        <span v-if="value"
          >{{ value.article_name }} - {{ value.order_code_1 }} - {{ value.manufacturer_name }}
          <ArchivedOptionTag v-if="value.archived" />
        </span>
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

.item-option-refused {
  pointer-events: auto;
}

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

.item-manufacturer {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
