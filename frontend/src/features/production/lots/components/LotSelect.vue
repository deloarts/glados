<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useRemoteOptions } from '@/shared/composables/useRemoteOptions'
import { getLots } from '../../api/getLots'
import { lotStatusSeverity } from '../../utils/lotStatus'
import { canDemandSourceItem } from '../utils/lotSourceEligibility'
import { useMadeItemLabel } from '@/features/made-items'

import type { LotSummaryResponse } from '../../types/productionLotsResponse'

interface Props {
  placeholder?: string
  excludeId?: number
  /**
   * Narrows the list to lots a source item demand can be created for, so the
   * user does not find out on submit.
   */
  demandableOnly?: boolean
}

const props = defineProps<Props>()

const model = defineModel<LotSummaryResponse | null>({ default: null })

const { t } = useI18n()
const { format: madeItemLabel } = useMadeItemLabel()

// Larger than the usual 20, since demandableOnly filters the page further.
const PAGE_SIZE = 50

function lotSublabel(lot: LotSummaryResponse): string {
  return [
    madeItemLabel(lot.made_item_part_number, lot.made_item_revision),
    lot.made_item_article_name,
    lot.made_item_material,
    lot.project_number,
  ]
    .filter(Boolean)
    .join(' | ')
}

const {
  items: lots,
  loading,
  debouncedSearch,
} = useRemoteOptions(
  async (query: string): Promise<LotSummaryResponse[]> => {
    const result = await getLots({
      limit: PAGE_SIZE,
      ...(query ? { search: query } : {}),
      // Server-side pre-filter, paired with canDemandSourceItem() below.
      ...(props.demandableOnly ? { actionable_for: 'source' as const } : {}),
    })
    let next = result.items
    if (props.demandableOnly) next = next.filter(canDemandSourceItem)
    if (props.excludeId != null) next = next.filter((lot) => lot.id !== props.excludeId)
    return next
  },
  // Keeps the selected lot in the options when a search does not return it.
  { keepSelected: model },
)

// The template root is a single element, so a disable comment in front
// of it would turn the root into a fragment and stop attribute fallthrough.
/* eslint-disable vuejs-accessibility/form-control-has-label -- the caller labels it, aria-labelledby falls through to the Select */
</script>

<template>
  <Select
    v-model="model"
    :options="lots"
    data-key="id"
    :loading="loading"
    :filter="true"
    :filter-fields="[
      'lot_number',
      'made_item_part_number',
      'made_item_article_name',
      'project_number',
    ]"
    :placeholder="props.placeholder ?? t('production.lots.select.placeholder')"
    show-clear
    @filter="(e) => debouncedSearch(e.value)"
  >
    <template #option="{ option }">
      <div class="lot-option">
        <span class="lot-number">
          {{ option.lot_number }}
          <Tag
            :value="t(`production.lots.status.${option.status}`)"
            :severity="lotStatusSeverity[option.status as keyof typeof lotStatusSeverity]"
          />
        </span>
        <span v-if="lotSublabel(option)" class="lot-sub">{{ lotSublabel(option) }}</span>
      </div>
    </template>
    <template #value="{ value }">
      <span v-if="value"
        >{{ value.lot_number }} -
        {{
          value.made_item_part_number
            ? madeItemLabel(value.made_item_part_number, value.made_item_revision)
            : value.made_item_article_name
        }}</span
      >
    </template>
    <template #empty>
      <span>{{ t('production.lots.select.empty') }}</span>
    </template>
  </Select>
</template>

<style scoped lang="scss">
.lot-option {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.lot-number {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-weight: 600;
  font-size: var(--font-size-sm);
}

.lot-sub {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
