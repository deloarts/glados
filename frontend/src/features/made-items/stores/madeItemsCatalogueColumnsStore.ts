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
import type { MadeItemDataSource, MadeItemFilterParams } from '../types/madeItemsRequest'
import type { MadeItemCatalogueStatus, MadeItemResponse } from '../types/madeItemsResponse'

export type { DateRangeFilters }

/**
 * text and number map to ilike or equals, status and data-source to an
 * equals filter, date-range to from/to params, and article-group to a Select.
 */
export type MadeItemColumnFilterType =
  | 'text'
  | 'number'
  | 'status'
  | 'data-source'
  | 'date-range'
  | 'article-group'

/**
 * Every response field plus the synthetic image and files columns, which
 * are never filtered or sorted.
 */
export type MadeItemColumnField = (keyof MadeItemResponse & string) | 'image' | 'files'

export type MadeItemRawColumn = CatalogueRawColumn<MadeItemColumnField, MadeItemColumnFilterType>
export type MadeItemColumnDefinition = CatalogueColumnDefinition<
  MadeItemColumnField,
  MadeItemColumnFilterType
>

export const MADE_ITEM_STATUS_OPTIONS: MadeItemCatalogueStatus[] = [
  'active',
  'inactive',
  'replaced',
]

export const MADE_ITEM_DATA_SOURCE_OPTIONS: MadeItemDataSource[] = ['WEB', 'CAD']

const FILTER_CONFIG = {
  filterMatchModes: {
    text: FilterMatchMode.CONTAINS,
    number: FilterMatchMode.EQUALS,
    status: FilterMatchMode.EQUALS,
    'data-source': FilterMatchMode.EQUALS,
    'article-group': FilterMatchMode.EQUALS,
  },
  numericFilterTypes: new Set<MadeItemColumnFilterType>(['number', 'article-group']),
}

/** Declaration order is the table's left-to-right column order. */
export const MADE_ITEMS_CATALOGUE_COLUMNS: MadeItemRawColumn[] = [
  { field: 'id', headerKey: 'madeItems.catalogue.columns.id', filter: 'number' },
  {
    field: 'status',
    headerKey: 'madeItems.catalogue.columns.status',
    filter: 'status',
    phone: true,
  },
  {
    field: 'successor_item_id',
    headerKey: 'madeItems.catalogue.columns.successorItem',
    filter: 'number',
  },
  { field: 'image', headerKey: 'madeItems.catalogue.columns.image', phone: 'thumbnail' },
  {
    field: 'part_number',
    headerKey: 'madeItems.catalogue.columns.partNumber',
    filter: 'text',
    phone: true,
  },
  { field: 'revision', headerKey: 'madeItems.catalogue.columns.revision', filter: 'text' },
  { field: 'revision_date', headerKey: 'madeItems.catalogue.columns.revisionDate' },
  { field: 'revision_note', headerKey: 'madeItems.catalogue.columns.revisionNote' },
  {
    field: 'article_name',
    headerKey: 'madeItems.catalogue.columns.articleName',
    filter: 'text',
    phone: true,
  },
  { field: 'material', headerKey: 'madeItems.catalogue.columns.material', filter: 'text' },
  { field: 'mass', headerKey: 'madeItems.catalogue.columns.mass', filter: 'number' },
  { field: 'processes', headerKey: 'madeItems.catalogue.columns.processes' },
  { field: 'files', headerKey: 'madeItems.catalogue.columns.files' },
  { field: 'base_size', headerKey: 'madeItems.catalogue.columns.baseSize' },
  { field: 'source_label', headerKey: 'madeItems.catalogue.columns.source' },
  { field: 'customer_name', headerKey: 'madeItems.catalogue.columns.customer' },
  {
    field: 'customer_part_number',
    headerKey: 'madeItems.catalogue.columns.customerPartNumber',
  },
  { field: 'customer_revision', headerKey: 'madeItems.catalogue.columns.customerRevision' },
  {
    field: 'article_groups',
    headerKey: 'madeItems.catalogue.columns.groups',
    filter: 'article-group',
    filterParamField: 'article_group_id',
  },
  { field: 'note', headerKey: 'madeItems.catalogue.columns.note', filter: 'text' },
  { field: 'weblink', headerKey: 'madeItems.catalogue.columns.weblink', filter: 'text' },
  {
    field: 'created',
    headerKey: 'madeItems.catalogue.columns.created',
    filter: 'date-range',
    userFilterParam: 'creator_id',
  },
  { field: 'changed', headerKey: 'madeItems.catalogue.columns.changed', filter: 'date-range' },
  {
    field: 'data_source',
    headerKey: 'madeItems.catalogue.columns.dataSource',
    filter: 'data-source',
  },
  { field: 'public_id', headerKey: 'madeItems.catalogue.columns.publicId' },
]

const DEFAULT_VISIBLE_FIELDS: MadeItemColumnDefinition['field'][] = [
  'id',
  'status',
  'image',
  'part_number',
  'revision',
  'article_name',
  'material',
  'mass',
  'processes',
  'files',
  'base_size',
  'source_label',
  'article_groups',
  'note',
]

export function createEmptyMadeItemFilters(): DataTableFilterMeta {
  return createEmptyCatalogueFilters(MADE_ITEMS_CATALOGUE_COLUMNS, FILTER_CONFIG)
}

export function createEmptyDateRangeFilters(): DateRangeFilters {
  return createEmptyDateRangeFiltersFor(MADE_ITEMS_CATALOGUE_COLUMNS)
}

export function toMadeItemFilterParams(
  filters: DataTableFilterMeta,
): Omit<MadeItemFilterParams, 'skip' | 'limit'> {
  return toCatalogueFilterParams(filters, MADE_ITEMS_CATALOGUE_COLUMNS, FILTER_CONFIG) as Omit<
    MadeItemFilterParams,
    'skip' | 'limit'
  >
}

export function toDateRangeFilterParams(
  dateRangeFilters: DateRangeFilters,
): Partial<
  Pick<MadeItemFilterParams, 'created_from' | 'created_to' | 'changed_from' | 'changed_to'>
> {
  return toDateRangeFilterParamsGeneric(dateRangeFilters)
}

export const useMadeItemsCatalogueColumnsStore = createCatalogueColumnsStore(
  'madeItemsCatalogueColumns',
  { columns: MADE_ITEMS_CATALOGUE_COLUMNS, defaultVisibleFields: DEFAULT_VISIBLE_FIELDS },
)
