<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { useServerTable } from '@/core/composables/useServerTable'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import type { ProjectRef } from '@/core/types/projectRef'
import { useProductsStore } from '@/features/products'
import EmptyState from '@/shared/components/EmptyState.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import ProjectSelect from '@/shared/components/project/ProjectSelect.vue'
import { getCalculations } from '../api/getCalculations'
import { toolByKey } from '../registry'
import type {
  CalculationListParams,
  CalculationOwner,
  CalculationSummaryResponse,
} from '../types/calculation'

/**
 * One tool's saved calculations, a page at a time. Every filter (title,
 * owner kind, project, product, status) is applied by the server, so the
 * pages stay complete. Lives inside the load dialog, so it mounts (and
 * loads) when the dialog opens.
 */

const props = defineProps<{
  tool: string
}>()

const emit = defineEmits<{ select: [calculation: CalculationSummaryResponse] }>()

const { t } = useI18n()

const items = ref<CalculationSummaryResponse[]>([])
const total = ref(0)
const search = ref('')
const ownerKind = ref<CalculationOwner['kind'] | null>(null)
const project = ref<ProjectRef | null>(null)
const productId = ref<number | null>(null)
const status = ref<'draft' | 'released' | null>(null)

const productsStore = useProductsStore()
onMounted(() => {
  if (!productsStore.items.length) void productsStore.refresh()
})

const ownerOptions = computed(() =>
  (['personal', 'project', 'product'] as const).map((value) => ({
    value,
    label: t(`tools.calculations.owner.${value}`),
  })),
)
const productOptions = computed(() =>
  productsStore.items.map((p) => ({
    value: p.id,
    label: p.description ? `${p.product_number} - ${p.description}` : p.product_number,
  })),
)
const statusOptions = computed(() =>
  (['draft', 'released'] as const).map((value) => ({
    value,
    label: t(`tools.calculations.status.${value}`),
  })),
)

// A specific project or product only makes sense next to a matching owner kind.
watch(ownerKind, (kind) => {
  if (kind !== null && kind !== 'project') project.value = null
  if (kind !== null && kind !== 'product') productId.value = null
})

// A late response for an earlier page or search must not replace a newer one.
const listFetch = useSequencedFetch(getCalculations)
const { loading, failed } = listFetch

async function fetch(query: CalculationListParams): Promise<void> {
  const page = await listFetch.run(query)
  if (!page) return
  items.value = page.items
  total.value = page.total
}

const { first, rows, onPage, resetAndFetch, resetAndFetchDebounced } = useServerTable<CalculationListParams>({
  fetchParams: (page) => {
    const params: CalculationListParams = { tool: props.tool, skip: page.first, limit: page.rows }
    if (search.value.trim()) params.search = search.value.trim()
    if (ownerKind.value) params.owner = ownerKind.value
    if (project.value) params.project_id = project.value.id
    if (productId.value !== null) params.product_id = productId.value
    if (status.value) params.released = status.value === 'released'
    return params
  },
  fetch,
})

watch(search, resetAndFetchDebounced)
watch([ownerKind, () => project.value?.id, productId, status], resetAndFetch)

function summary(row: CalculationSummaryResponse): string {
  return toolByKey(row.tool)?.summarize(row.results, t) ?? ''
}

function owner(row: CalculationSummaryResponse): string {
  if (row.project_number) return `${t('tools.calculations.owner.project')} ${row.project_number}`
  if (row.product_number) return `${t('tools.calculations.owner.product')} ${row.product_number}`
  return `${t('tools.calculations.owner.personal')} (${row.creator_full_name})`
}
</script>

<template>
  <div class="load">
    <div class="filters">
      <div class="filter">
        <label for="calc-load-search">{{ t('tools.calculations.list.title') }}</label>
        <IconField>
          <InputIcon class="mdi mdi-magnify" />
          <InputText
            id="calc-load-search"
            v-model="search"
            :placeholder="t('tools.calculations.filters.search')"
            fluid
            data-testid="calc-load-search"
          />
        </IconField>
      </div>
      <div class="filter">
        <label id="calc-load-owner-label" for="calc-load-owner">{{ t('tools.calculations.list.owner') }}</label>
        <Select
          v-model="ownerKind"
          input-id="calc-load-owner"
          aria-labelledby="calc-load-owner-label"
          :options="ownerOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('tools.calculations.filters.anyOwner')"
          show-clear
          fluid
          data-testid="calc-load-owner"
        />
      </div>
      <div class="filter">
        <label id="calc-load-project-label" for="calc-load-project">{{ t('tools.calculations.owner.project') }}</label>
        <ProjectSelect
          v-model="project"
          input-id="calc-load-project"
          aria-labelledby="calc-load-project-label"
          :disabled="ownerKind !== null && ownerKind !== 'project'"
        />
      </div>
      <div class="filter">
        <label id="calc-load-product-label" for="calc-load-product">{{ t('tools.calculations.owner.product') }}</label>
        <Select
          v-model="productId"
          input-id="calc-load-product"
          aria-labelledby="calc-load-product-label"
          :options="productOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('tools.calculations.filters.anyProduct')"
          :disabled="ownerKind !== null && ownerKind !== 'product'"
          :loading="productsStore.loading"
          filter
          show-clear
          fluid
        />
      </div>
      <div class="filter">
        <label id="calc-load-status-label" for="calc-load-status">{{ t('tools.calculations.list.status') }}</label>
        <Select
          v-model="status"
          input-id="calc-load-status"
          aria-labelledby="calc-load-status-label"
          :options="statusOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('tools.calculations.filters.anyStatus')"
          show-clear
          fluid
          data-testid="calc-load-status"
        />
      </div>
    </div>
    <Message v-if="failed" severity="error">{{ t('tools.calculations.errors.loadList') }}</Message>
    <DataTable
      :value="items"
      :loading="loading"
      lazy
      paginator
      :first="first"
      :rows="rows"
      :total-records="total"
      :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
      data-key="id"
      size="small"
      scrollable
      scroll-height="24rem"
      selection-mode="single"
      @page="onPage"
      @row-select="(e) => emit('select', e.data)"
    >
      <template #empty>
        <EmptyState icon="mdi mdi-calculator-variant-outline" :message="t('tools.calculations.list.empty')" />
      </template>
      <Column :header="t('tools.calculations.list.title')">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <span class="title" :data-testid="`calc-load-row-${data.id}`">{{ data.title }}</span>
          <div class="summary">{{ summary(data) }}</div>
        </template>
      </Column>
      <Column :header="t('tools.calculations.list.owner')" style="width: 13rem">
        <template #body="{ data }: { data: CalculationSummaryResponse }">{{ owner(data) }}</template>
      </Column>
      <Column :header="t('tools.calculations.list.status')" style="width: 8rem">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <Tag
            :value="t(`tools.calculations.status.${data.released_at ? 'released' : 'draft'}`)"
            :severity="data.released_at ? 'success' : 'secondary'"
          />
        </template>
      </Column>
      <Column :header="t('tools.calculations.list.changed')" style="width: 9rem">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <UserDateCell
            :date="data.changed ?? data.created"
            :user-id="data.changed ? data.changed_by_id : data.creator_id"
            :name="data.changed ? data.changed_by_full_name : data.creator_full_name"
          />
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<style scoped lang="scss">
.load {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
  gap: var(--space-2) var(--space-3);
}

.filter {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;

  label {
    font-size: var(--font-size-sm);
    color: var(--p-text-muted-color);
  }
}

.title {
  font-weight: 600;
}

.summary {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
