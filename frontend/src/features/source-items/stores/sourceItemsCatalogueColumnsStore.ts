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
import type { SourceItemFilterParams } from '../types/sourceItemsRequest'
import type { SourceItemCatalogueStatus, SourceItemResponse } from '../types/sourceItemsResponse'

export type { DateRangeFilters }

/**
 * text and number map to ilike or equals, status to an equals filter, and
 * date-range to from/to params. Columns without a filter are display-only.
 */
export type SourceItemColumnFilterType =
  | 'text'
  | 'number'
  | 'status'
  | 'date-range'
  | 'supplier'
  | 'source-item-type'

/**
 * image and files are synthetic columns rendered from the files store,
 * hideable and reorderable like any other.
 */
export type SourceItemColumnField = (keyof SourceItemResponse & string) | 'image' | 'files'

export type SourceItemRawColumn = CatalogueRawColumn<
  SourceItemColumnField,
  SourceItemColumnFilterType
>
export type SourceItemColumnDefinition = CatalogueColumnDefinition<
  SourceItemColumnField,
  SourceItemColumnFilterType
>

export const SOURCE_ITEM_STATUS_OPTIONS: SourceItemCatalogueStatus[] = [
  'active',
  'inactive',
  'replaced',
]

const FILTER_CONFIG = {
  filterMatchModes: {
    text: FilterMatchMode.CONTAINS,
    number: FilterMatchMode.EQUALS,
    status: FilterMatchMode.EQUALS,
    supplier: FilterMatchMode.EQUALS,
    'source-item-type': FilterMatchMode.EQUALS,
  },
  numericFilterTypes: new Set<SourceItemColumnFilterType>([
    'number',
    'supplier',
    'source-item-type',
  ]),
}

export const SOURCE_ITEMS_CATALOGUE_COLUMNS: SourceItemRawColumn[] = [
  { field: 'id', headerKey: 'sourceItems.catalogue.columns.id', filter: 'number' },
  { field: 'image', headerKey: 'sourceItems.catalogue.columns.image', phone: 'thumbnail' },
  { field: 'files', headerKey: 'sourceItems.catalogue.columns.files' },
  { field: 'status', headerKey: 'sourceItems.catalogue.columns.status', filter: 'status' },
  {
    field: 'dimension',
    headerKey: 'sourceItems.catalogue.columns.dimension',
    filter: 'text',
    phone: true,
  },
  {
    field: 'material',
    headerKey: 'sourceItems.catalogue.columns.material',
    filter: 'text',
    phone: true,
  },
  {
    field: 'type_name',
    headerKey: 'sourceItems.catalogue.columns.type',
    filter: 'source-item-type',
    filterParamField: 'type_id',
    phone: true,
  },
  { field: 'mass', headerKey: 'sourceItems.catalogue.columns.mass', filter: 'number' },
  {
    field: 'order_code_1',
    headerKey: 'sourceItems.catalogue.columns.orderCode1',
    filter: 'text',
  },
  {
    field: 'order_code_2',
    headerKey: 'sourceItems.catalogue.columns.orderCode2',
    filter: 'text',
  },
  {
    field: 'manufacturer_name',
    headerKey: 'sourceItems.catalogue.columns.manufacturer',
    filter: 'supplier',
    filterParamField: 'manufacturer_id',
  },
  {
    field: 'successor_item_id',
    headerKey: 'sourceItems.catalogue.columns.successorItem',
    filter: 'number',
  },
  { field: 'note', headerKey: 'sourceItems.catalogue.columns.note', filter: 'text' },
  {
    field: 'created',
    headerKey: 'sourceItems.catalogue.columns.created',
    filter: 'date-range',
    userFilterParam: 'creator_id',
  },
  {
    field: 'changed',
    headerKey: 'sourceItems.catalogue.columns.changed',
    filter: 'date-range',
    userFilterParam: 'changed_by_id',
  },
]

const DEFAULT_VISIBLE_FIELDS: SourceItemColumnDefinition['field'][] = [
  'id',
  'image',
  'files',
  'status',
  'dimension',
  'material',
  'type_name',
  'mass',
  'order_code_1',
  'order_code_2',
  'manufacturer_name',
  'note',
]

export function createEmptySourceItemFilters(): DataTableFilterMeta {
  return createEmptyCatalogueFilters(SOURCE_ITEMS_CATALOGUE_COLUMNS, FILTER_CONFIG)
}

export function createEmptyDateRangeFilters(): DateRangeFilters {
  return createEmptyDateRangeFiltersFor(SOURCE_ITEMS_CATALOGUE_COLUMNS)
}

export function toSourceItemFilterParams(
  filters: DataTableFilterMeta,
): Omit<SourceItemFilterParams, 'skip' | 'limit'> {
  return toCatalogueFilterParams(filters, SOURCE_ITEMS_CATALOGUE_COLUMNS, FILTER_CONFIG) as Omit<
    SourceItemFilterParams,
    'skip' | 'limit'
  >
}

export function toDateRangeFilterParams(
  dateRangeFilters: DateRangeFilters,
): Partial<
  Pick<SourceItemFilterParams, 'created_from' | 'created_to' | 'changed_from' | 'changed_to'>
> {
  return toDateRangeFilterParamsGeneric(dateRangeFilters)
}

export const useSourceItemsCatalogueColumnsStore = createCatalogueColumnsStore(
  'sourceItemsCatalogueColumns',
  { columns: SOURCE_ITEMS_CATALOGUE_COLUMNS, defaultVisibleFields: DEFAULT_VISIBLE_FIELDS },
)
