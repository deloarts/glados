<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { getLots } from '@/features/production'
import { getProducts } from '@/features/products'
import {
  fetchDemandProjectOptions,
  fetchDemandProjectsByIds,
} from '@/shared/components/demands/demandProjectLookup'
import LookupMultiSelect from '@/shared/components/forms/LookupMultiSelect.vue'

import type { LookupFetchByIds, LookupOption } from '@/shared/components/forms/lookupMultiSelect'

/**
 * The row filter of the lot column of the external work list, built like
 * the user and date filter: one small field sums up the lots, projects and
 * products picked and opens a panel with a multi select for each. The three
 * narrow the list together.
 */
const props = defineProps<{
  /** Names the column in the accessible labels. */
  column: string
  /** Shown while nothing is set, the table's usual "any" text. */
  placeholder?: string
}>()

const lotIds = defineModel<number[]>('lotIds', { default: () => [] })
const projectIds = defineModel<number[]>('projectIds', { default: () => [] })
const productIds = defineModel<number[]>('productIds', { default: () => [] })

const { t } = useI18n()
const popover = ref<{ toggle: (event: Event) => void } | null>(null)

function toLotOption(lot: { id: number; lot_number: string; made_item_article_name: string }): LookupOption {
  return { id: lot.id, label: lot.lot_number, sublabel: lot.made_item_article_name }
}

async function fetchLotOptions(query: string): Promise<LookupOption[]> {
  const page = await getLots({ search: query || undefined, limit: 15 })
  return page.items.map(toLotOption)
}

async function fetchLotsByIds(ids: number[]): Promise<LookupOption[]> {
  const page = await getLots({ ids, limit: ids.length })
  return page.items.map(toLotOption)
}

function toProductOption(product: { id: number; product_number: string; description?: string | null }): LookupOption {
  return {
    id: product.id,
    label: product.product_number,
    ...(product.description ? { sublabel: product.description } : {}),
  }
}

async function fetchProductOptions(query: string): Promise<LookupOption[]> {
  const page = await getProducts({ limit: 20, ...(query ? { search: query } : {}) })
  return page.items.map(toProductOption)
}

// The product list filters by one id, and a filter holds only a few.
async function fetchProductsByIds(ids: number[]): Promise<LookupOption[]> {
  const pages = await Promise.all(ids.map((id) => getProducts({ id, limit: 1 })))
  return pages.flatMap((page) => page.items.map(toProductOption))
}

// The labels of what is picked, for the summary field.
const labels = ref<Record<'lots' | 'projects' | 'products', string[]>>({
  lots: [],
  projects: [],
  products: [],
})

function resolveLabels(
  key: 'lots' | 'projects' | 'products',
  ids: () => number[],
  fetchByIds: LookupFetchByIds,
): void {
  watch(
    ids,
    async (picked) => {
      if (picked.length === 0) {
        labels.value[key] = []
        return
      }
      try {
        labels.value[key] = (await fetchByIds(picked)).map((option) => option.label)
      } catch {
        labels.value[key] = picked.map(String)
      }
    },
    { immediate: true, deep: true },
  )
}

resolveLabels('lots', () => lotIds.value, fetchLotsByIds)
resolveLabels('projects', () => projectIds.value, fetchDemandProjectsByIds)
resolveLabels('products', () => productIds.value, fetchProductsByIds)

const summary = computed(() =>
  [...labels.value.lots, ...labels.value.projects, ...labels.value.products].join(', '),
)
const hasValue = computed(
  () => lotIds.value.length > 0 || projectIds.value.length > 0 || productIds.value.length > 0,
)

function toggle(event: Event): void {
  popover.value?.toggle(event)
}

function clear(): void {
  lotIds.value = []
  projectIds.value = []
  productIds.value = []
}
</script>

<template>
  <div class="lot-filter">
    <IconField>
      <InputText
        :model-value="summary"
        readonly
        :placeholder="props.placeholder ?? t('procurement.externalWork.filters.any')"
        :title="summary || undefined"
        :aria-label="t('common.filterBy', { column })"
        aria-haspopup="dialog"
        size="small"
        fluid
        class="lot-filter-field"
        data-testid="external-work-lot-filter-field"
        @click="toggle"
        @keydown.enter.prevent="toggle"
        @keydown.space.prevent="toggle"
      />
      <InputIcon
        v-if="hasValue"
        class="mdi mdi-close lot-filter-clear"
        role="button"
        tabindex="0"
        :aria-label="t('common.clear')"
        data-testid="external-work-lot-filter-clear"
        @click.stop="clear"
        @keydown.enter.prevent="clear"
      />
    </IconField>

    <Popover ref="popover">
      <div class="lot-filter-panel" data-testid="external-work-lot-filter-panel">
        <LookupMultiSelect
          v-model="lotIds"
          :aria-label="t('procurement.externalWork.filters.lot')"
          :fetch="fetchLotOptions"
          :fetch-by-ids="fetchLotsByIds"
          :placeholder="t('procurement.externalWork.filters.lot')"
          :compact="false"
        />
        <LookupMultiSelect
          v-model="projectIds"
          :aria-label="t('procurement.externalWork.filters.project')"
          :fetch="fetchDemandProjectOptions"
          :fetch-by-ids="fetchDemandProjectsByIds"
          :placeholder="t('procurement.externalWork.filters.project')"
          :compact="false"
        />
        <LookupMultiSelect
          v-model="productIds"
          :aria-label="t('procurement.externalWork.filters.product')"
          :fetch="fetchProductOptions"
          :fetch-by-ids="fetchProductsByIds"
          :placeholder="t('procurement.externalWork.filters.product')"
          :compact="false"
        />
      </div>
    </Popover>
  </div>
</template>

<style scoped lang="scss">
.lot-filter {
  min-width: 0;
}

.lot-filter-field {
  cursor: pointer;
  text-overflow: ellipsis;
}

.lot-filter-clear {
  cursor: pointer;
}

.lot-filter-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 18rem;
}
</style>
