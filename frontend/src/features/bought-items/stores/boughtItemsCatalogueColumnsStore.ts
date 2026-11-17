import { FilterMatchMode } from '@openvue/core/api'

import {
  createCatalogueColumnsStore,
  createEmptyCatalogueFilters,
  createEmptyDateRangeFilters as createEmptyDateRangeFiltersFor,
  toCatalogueFilterParams,
  toDateRangeFilterParams as toDateRangeFilterParamsGeneric,
} from '@/shared/stores/createCatalogueColumnsStore'

import type {
  CatalogueColumnDefinition,
  CatalogueRawColumn,
  DateRangeFilters,
} from '@/shared/stores/createCatalogueColumnsStore'
import type { DataTableFilterMeta } from 'openvue/datatable'
import type { BoughtItemDataSource, BoughtItemFilterParams } from '../types/boughtItemsRequest'
import type { BoughtItemCatalogueStatus, BoughtItemResponse } from '../types/boughtItemsResponse'

export type { DateRangeFilters }

/**
 * text and number map to ilike or equals, status to an equals filter,
 * date-range to from/to params, and article-group and product-family to a
 * Select sending the id through filterParamField. Columns without a filter are display-only.
 */
export type BoughtItemColumnFilterType =
  | 'text'
  | 'number'
  | 'status'
  | 'date-range'
  | 'article-group'
  | 'product-family'
  | 'supplier'
  | 'data-source'

export type BoughtItemRawColumn = CatalogueRawColumn<
  keyof BoughtItemResponse & string,
  BoughtItemColumnFilterType
>
export type BoughtItemColumnDefinition = CatalogueColumnDefinition<
  keyof BoughtItemResponse & string,
  BoughtItemColumnFilterType
>

export const BOUGHT_ITEM_STATUS_OPTIONS: BoughtItemCatalogueStatus[] = [
  'active',
  'inactive',
  'replaced',
]

export const BOUGHT_ITEM_DATA_SOURCE_OPTIONS: BoughtItemDataSource[] = ['WEB', 'CAD']

const FILTER_CONFIG = {
  filterMatchModes: {
    text: FilterMatchMode.CONTAINS,
    number: FilterMatchMode.EQUALS,
    status: FilterMatchMode.EQUALS,
    'data-source': FilterMatchMode.EQUALS,
    'article-group': FilterMatchMode.EQUALS,
    'product-family': FilterMatchMode.EQUALS,
    supplier: FilterMatchMode.EQUALS,
  },
  numericFilterTypes: new Set<BoughtItemColumnFilterType>([
    'number',
    'article-group',
    'product-family',
    'supplier',
  ]),
}

export const BOUGHT_ITEMS_CATALOGUE_COLUMNS: BoughtItemRawColumn[] = [
  { field: 'id', headerKey: 'boughtItems.catalogue.columns.id', filter: 'number' },
  {
    field: 'status',
    headerKey: 'boughtItems.catalogue.columns.status',
    filter: 'status',
    phone: true,
  },
  {
    field: 'data_source',
    headerKey: 'boughtItems.catalogue.columns.dataSource',
    filter: 'data-source',
  },
  {
    field: 'successor_item_id',
    headerKey: 'boughtItems.catalogue.columns.successorItem',
    filter: 'number',
  },
  {
    field: 'article_name',
    headerKey: 'boughtItems.catalogue.columns.articleName',
    filter: 'text',
    phone: true,
  },
  {
    field: 'part_number',
    headerKey: 'boughtItems.catalogue.columns.partNumber',
    filter: 'text',
    phone: true,
  },
  // PDM-owned and read-only, without a backend filter; hidden by default.
  { field: 'revision', headerKey: 'boughtItems.catalogue.columns.revision' },
  { field: 'order_code_1', headerKey: 'boughtItems.catalogue.columns.orderCode1', filter: 'text' },
  { field: 'order_code_2', headerKey: 'boughtItems.catalogue.columns.orderCode2', filter: 'text' },
  {
    field: 'manufacturer_name',
    headerKey: 'boughtItems.catalogue.columns.manufacturer',
    filter: 'supplier',
    filterParamField: 'manufacturer_id',
  },
  {
    field: 'article_groups',
    headerKey: 'boughtItems.catalogue.columns.groups',
    filter: 'article-group',
    filterParamField: 'article_group_id',
  },
  {
    field: 'product_family',
    headerKey: 'boughtItems.catalogue.columns.productFamily',
    filter: 'product-family',
    filterParamField: 'product_family_id',
  },
  { field: 'pdf_files', headerKey: 'boughtItems.catalogue.columns.files' },
  { field: 'note', headerKey: 'boughtItems.catalogue.columns.note', filter: 'text' },
  { field: 'gtin', headerKey: 'boughtItems.catalogue.columns.gtin', filter: 'text' },
  { field: 'ean', headerKey: 'boughtItems.catalogue.columns.ean', filter: 'text' },
  {
    field: 'tariff_number',
    headerKey: 'boughtItems.catalogue.columns.tariffNumber',
    filter: 'text',
  },
  { field: 'mass', headerKey: 'boughtItems.catalogue.columns.mass', filter: 'number' },
  { field: 'weblink', headerKey: 'boughtItems.catalogue.columns.weblink', filter: 'text' },
  {
    field: 'created',
    headerKey: 'boughtItems.catalogue.columns.created',
    filter: 'date-range',
    userFilterParam: 'creator_id',
  },
  {
    field: 'changed',
    headerKey: 'boughtItems.catalogue.columns.changed',
    filter: 'date-range',
    userFilterParam: 'changed_by_id',
  },
]

const DEFAULT_VISIBLE_FIELDS: BoughtItemColumnDefinition['field'][] = [
  'id',
  'status',
  'data_source',
  'article_name',
  'part_number',
  'order_code_1',
  'order_code_2',
  'manufacturer_name',
  'article_groups',
  'product_family',
  'pdf_files',
  'note',
  'weblink',
]

export function createEmptyBoughtItemFilters(): DataTableFilterMeta {
  return createEmptyCatalogueFilters(BOUGHT_ITEMS_CATALOGUE_COLUMNS, FILTER_CONFIG)
}

export function createEmptyDateRangeFilters(): DateRangeFilters {
  return createEmptyDateRangeFiltersFor(BOUGHT_ITEMS_CATALOGUE_COLUMNS)
}

export function toBoughtItemFilterParams(
  filters: DataTableFilterMeta,
): Omit<BoughtItemFilterParams, 'skip' | 'limit'> {
  return toCatalogueFilterParams(filters, BOUGHT_ITEMS_CATALOGUE_COLUMNS, FILTER_CONFIG) as Omit<
    BoughtItemFilterParams,
    'skip' | 'limit'
  >
}

export function toDateRangeFilterParams(
  dateRangeFilters: DateRangeFilters,
): Partial<
  Pick<BoughtItemFilterParams, 'created_from' | 'created_to' | 'changed_from' | 'changed_to'>
> {
  return toDateRangeFilterParamsGeneric(dateRangeFilters)
}

export const useBoughtItemsCatalogueColumnsStore = createCatalogueColumnsStore(
  'boughtItemsCatalogueColumns',
  { columns: BOUGHT_ITEMS_CATALOGUE_COLUMNS, defaultVisibleFields: DEFAULT_VISIBLE_FIELDS },
)
