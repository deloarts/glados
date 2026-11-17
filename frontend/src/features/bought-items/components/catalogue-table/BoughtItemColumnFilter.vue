<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useArticleGroupsStore } from '@/features/article-groups'
import { useProductFamiliesStore } from '@/features/product-families'
import { SupplierSearchFilter } from '@/features/suppliers'
import {
  BOUGHT_ITEM_DATA_SOURCE_OPTIONS,
  BOUGHT_ITEM_STATUS_OPTIONS,
} from '../../stores/boughtItemsCatalogueColumnsStore'

import type { BoughtItemColumnDefinition } from '../../stores/boughtItemsCatalogueColumnsStore'
import { labelName } from '@/shared/utils/localizeLabel'

// The filter control for a column's filter kind. Takes the value as a prop
// and emits it back, since the caller owns OpenVue's filterModel.
const props = defineProps<{
  column: BoughtItemColumnDefinition
  modelValue: unknown
  filterCallback: () => void
  getDateRangeModel: (field: string) => [Date, Date | null] | null
  setDateRangeModel: (field: string, value: Date | Array<Date | null> | null | undefined) => void
}>()

const emit = defineEmits<{
  'update:modelValue': [value: unknown]
}>()

const { t } = useI18n()
const articleGroupsStore = useArticleGroupsStore()
const productFamiliesStore = useProductFamiliesStore()

const statusOptions = computed(() =>
  BOUGHT_ITEM_STATUS_OPTIONS.map((s) => ({
    label: t(`boughtItems.catalogue.status.${s}`),
    value: s,
  })),
)

// "All" maps to null, which means no filter.
const dataSourceOptions = computed(() => [
  { label: t('boughtItems.catalogue.filters.all'), value: null },
  ...BOUGHT_ITEM_DATA_SOURCE_OPTIONS.map((source) => ({
    label: t(`boughtItems.catalogue.dataSources.${source}`),
    value: source,
  })),
])

const dateRangeModel = computed(() => props.getDateRangeModel(props.column.field))

// Narrows the unknown value per filter kind with a runtime check.
const numericModelValue = computed<number | null>(() => {
  const value = props.modelValue
  return typeof value === 'number' ? value : null
})

const textModelValue = computed<string | undefined>(() => {
  const value = props.modelValue
  return typeof value === 'string' ? value : undefined
})
</script>

<template>
  <Select
    v-if="column.filter === 'status'"
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :options="statusOptions"
    option-label="label"
    option-value="value"
    show-clear
    :placeholder="t('boughtItems.catalogue.filters.any')"
    :aria-label="t('common.filterBy', { column: column.header })"
    size="small"
    fluid
    @change="filterCallback()"
    @clear="filterCallback()"
  />
  <Select
    v-else-if="column.filter === 'data-source'"
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :options="dataSourceOptions"
    option-label="label"
    option-value="value"
    :placeholder="t('boughtItems.catalogue.filters.all')"
    :aria-label="t('common.filterBy', { column: column.header })"
    size="small"
    fluid
    @change="filterCallback()"
  />
  <SupplierSearchFilter
    v-else-if="column.filter === 'supplier'"
    :model-value="numericModelValue"
    @update:model-value="
      (v) => {
        emit('update:modelValue', v)
        filterCallback()
      }
    "
    :placeholder="t('boughtItems.catalogue.filters.any')"
    :aria-label="t('common.filterBy', { column: column.header })"
  />
  <Select
    v-else-if="column.filter === 'article-group'"
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :options="articleGroupsStore.items"
    :option-label="labelName"
    option-value="id"
    :loading="articleGroupsStore.loading"
    show-clear
    :placeholder="t('boughtItems.catalogue.filters.any')"
    :aria-label="t('common.filterBy', { column: column.header })"
    size="small"
    fluid
    @change="filterCallback()"
    @clear="filterCallback()"
  />
  <Select
    v-else-if="column.filter === 'product-family'"
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :options="productFamiliesStore.items"
    :option-label="labelName"
    option-value="id"
    :loading="productFamiliesStore.loading"
    show-clear
    filter
    :placeholder="t('boughtItems.catalogue.filters.any')"
    :aria-label="t('common.filterBy', { column: column.header })"
    size="small"
    fluid
    @change="filterCallback()"
    @clear="filterCallback()"
  />
  <DatePicker
    v-else-if="column.filter === 'date-range'"
    :model-value="dateRangeModel"
    selection-mode="range"
    show-button-bar
    show-clear
    :placeholder="`${t('boughtItems.catalogue.filters.filterBy')} ${column.header}`"
    :aria-label="t('common.filterBy', { column: column.header })"
    size="small"
    fluid
    @update:model-value="(value) => setDateRangeModel(column.field, value)"
    @clear-click="setDateRangeModel(column.field, null)"
  />
  <InputNumber
    v-else-if="column.filter === 'number'"
    :model-value="numericModelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :use-grouping="false"
    @input="filterCallback()"
    :placeholder="`${t('boughtItems.catalogue.filters.searchBy')} ${column.header}`"
    :aria-label="t('common.filterBy', { column: column.header })"
    size="small"
    fluid
  />
  <InputText
    v-else
    :model-value="textModelValue"
    @update:model-value="emit('update:modelValue', $event)"
    @input="filterCallback()"
    :placeholder="`${t('boughtItems.catalogue.filters.searchBy')} ${column.header}`"
    :aria-label="t('common.filterBy', { column: column.header })"
    size="small"
    fluid
  />
</template>
