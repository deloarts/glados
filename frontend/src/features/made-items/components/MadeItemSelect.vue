<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useHostStore } from '@/core/host/stores/hostStore'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import { useRemoteOptions } from '@/shared/composables/useRemoteOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { getMadeItems } from '../api/getMadeItems'
import MadeItemThumbnailCell from './MadeItemThumbnailCell.vue'
import { useMadeItemLabel } from '../utils/madeItemLabel'
import type { MadeItemResponse } from '../types/madeItemsResponse'
import { catalogueStatusTagSeverity } from '@/shared/utils/catalogueStatus'

interface Props {
  excludeId?: number
  /**
   * Replaces the catalogue search behind the options, for a caller that
   * offers its own candidates, e.g. a merge's targets.
   */
  fetchOptions?: (query: string) => Promise<MadeItemResponse[]>
  /**
   * Why an option may not be picked, null when it may. Such an option stays
   * listed, disabled, with the reason as its tooltip.
   */
  disabledReason?: (item: MadeItemResponse) => string | null
}

const props = defineProps<Props>()

// Single-rooted with attrs forwarded explicitly, so a parent's fluid still
// reaches the Select next to the archived warning.
defineOptions({ inheritAttrs: false })

const model = defineModel<MadeItemResponse | null>({ default: null })

const { t } = useI18n()

const hostStore = useHostStore()
const { format: madeItemLabel } = useMadeItemLabel()

async function searchCatalogue(query: string): Promise<MadeItemResponse[]> {
  const result = await getMadeItems({
    limit: 50,
    include_archived: true,
    ...(query ? { search: query } : {}),
  })
  return result.items
}

const { items, loading, debouncedSearch } = useRemoteOptions((query: string) =>
  (props.fetchOptions ?? searchCatalogue)(query),
)

function refusalOf(item: MadeItemResponse): string | null {
  return props.disabledReason?.(item) ?? null
}

const filteredItems = computed(() =>
  props.excludeId !== undefined ? items.value.filter((i) => i.id !== props.excludeId) : items.value,
)

// Archived items stay selectable, sorted last.
const { sortedOptions: options, isArchived } = useArchivableOptions(filteredItems)

function materialInfo(item: MadeItemResponse): string {
  const parts: string[] = []
  if (item.material) parts.push(item.material)
  if (item.mass !== null) parts.push(`${item.mass / 1000}kg`)
  return parts.join(', ')
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
      :filter-fields="['part_number', 'article_name']"
      :loading="loading"
      :option-disabled="(option: MadeItemResponse) => refusalOf(option) !== null"
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
          <MadeItemThumbnailCell
            v-if="hostStore.storageEnabled"
            :item-id="option.id"
            :item-name="option.article_name"
            no-image-icon="mdi mdi-image-outline"
            style="margin-right: var(--space-2)"
          />
          <div class="item-option">
            <span class="item-name"
              >{{ madeItemLabel(option.part_number, option.revision) }}
              <Tag
                :value="t(`madeItems.catalogue.status.${option.status}`)"
                :severity="catalogueStatusTagSeverity(option.status)"
              />
              <ArchivedOptionTag v-if="option.archived" />
            </span>
            <span class="item-code">{{ option.article_name }}</span>
            <span v-if="materialInfo(option)" class="item-material">{{ materialInfo(option) }}</span>
          </div>
        </div>
      </template>
      <template #value="{ value }">
        <span v-if="value"
          >{{ madeItemLabel(value.part_number, value.revision) }} - {{ value.article_name }}
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

.item-material {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
