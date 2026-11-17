import { computed, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import { useI18n } from 'vue-i18n'
import { toDateKey } from '@/core/utils/dates'
import { filterMetaValue } from '@/core/utils/filterMeta'

import type { DataTableFilterMeta } from 'openvue/datatable'

export interface CatalogueRawColumn<TField extends string, TFilterType extends string> {
  field: TField
  headerKey: string
  filter?: TFilterType
  /** Override the API query-param name when it differs from the column field. */
  filterParamField?: string
  /**
   * The API query param of the person a date column also filters by, such as
   * `creator_id` for the created column, which shows its creator below the
   * date. Its value sits in the filter model under this name.
   */
  userFilterParam?: string
  /**
   * One of the few columns a phone shows, see `phone-columns` in
   * `_openvue.scss`: `true` for a column that shares the width, `'thumbnail'`
   * for the narrow picture column.
   */
  phone?: true | 'thumbnail'
}

export interface CatalogueColumnDefinition<
  TField extends string,
  TFilterType extends string,
> extends CatalogueRawColumn<TField, TFilterType> {
  header: string
  /** The column's class for the phone layout, from `phone`. */
  phoneClass: PhoneColumnClass | undefined
}

type PhoneColumnClass = 'phone-col' | 'phone-thumbnail'

function phoneClassOf(phone: true | 'thumbnail' | undefined): PhoneColumnClass | undefined {
  if (phone === 'thumbnail') return 'phone-thumbnail'
  return phone ? 'phone-col' : undefined
}

export type DateRangeFilters = Record<string, [Date | null, Date | null]>

/**
 * A catalogue's filter config: the match mode per filter type and which
 * types are sent as numbers. This is where the catalogues differ.
 */
export interface CatalogueFilterConfig<TFilterType extends string> {
  filterMatchModes: Record<Exclude<TFilterType, 'date-range'>, string>
  numericFilterTypes: ReadonlySet<TFilterType>
}

/**
 * An empty filter model for the scalar columns. Date ranges are tracked
 * separately, because array values in OpenVue's filter model can trigger a
 * recursive update loop.
 */
export function createEmptyCatalogueFilters<TField extends string, TFilterType extends string>(
  columns: CatalogueRawColumn<TField, TFilterType>[],
  config: CatalogueFilterConfig<TFilterType>,
): DataTableFilterMeta {
  const filters: DataTableFilterMeta = {}

  for (const column of columns) {
    if (column.userFilterParam) {
      filters[column.userFilterParam] = { value: null, matchMode: 'equals' }
    }

    if (!column.filter || (column.filter as string) === 'date-range') {
      continue
    }

    filters[column.field] = {
      value: null,
      matchMode: config.filterMatchModes[column.filter as Exclude<TFilterType, 'date-range'>],
    }
  }

  return filters
}

/** An empty value map for the date-range columns. */
export function createEmptyDateRangeFilters<TField extends string, TFilterType extends string>(
  columns: CatalogueRawColumn<TField, TFilterType>[],
): DateRangeFilters {
  const filters: DateRangeFilters = {}

  for (const column of columns) {
    if ((column.filter as string) === 'date-range') {
      filters[column.field] = [null, null]
    }
  }

  return filters
}

/** Converts the scalar filters into API query params. */
export function toCatalogueFilterParams<TField extends string, TFilterType extends string>(
  filters: DataTableFilterMeta,
  columns: CatalogueRawColumn<TField, TFilterType>[],
  config: CatalogueFilterConfig<TFilterType>,
): Record<string, unknown> {
  const params: Record<string, unknown> = {}

  for (const column of columns) {
    if (column.userFilterParam) {
      const userId = filterMetaValue(filters, column.userFilterParam)
      if (userId !== null && userId !== undefined && userId !== '') {
        params[column.userFilterParam] = Number(userId)
      }
    }

    if (!column.filter || (column.filter as string) === 'date-range') {
      continue
    }

    const meta = filters[column.field]
    let value: unknown

    if (typeof meta === 'string') {
      value = meta
    } else if (Array.isArray(meta)) {
      // meta can be an array of operator metas
      value = meta[0]?.value
    } else if (meta && 'value' in meta) {
      // A plain filter meta. An operator meta carries `constraints` instead
      // and, like a missing one, leaves the value unset.
      value = meta.value
    }

    if (value === null || value === undefined || value === '') {
      continue
    }

    const paramField = column.filterParamField ?? column.field
    params[paramField] = config.numericFilterTypes.has(column.filter) ? Number(value) : value
  }

  return params
}

/** Converts date ranges into `${field}_from`/`${field}_to` params. */
export function toDateRangeFilterParams(
  dateRangeFilters: DateRangeFilters,
): Record<string, string> {
  const params: Record<string, string> = {}

  for (const [field, [from, to]] of Object.entries(dateRangeFilters)) {
    if (from) {
      params[`${field}_from`] = toDateKey(from)
    }
    if (to) {
      params[`${field}_to`] = toDateKey(to)
    }
  }

  return params
}

/**
 * The column visibility state of a catalogue table; the column list and
 * filter config come from the feature.
 */
export function createCatalogueColumnsStore<TField extends string, TFilterType extends string>(
  id: string,
  options: {
    columns: CatalogueRawColumn<TField, TFilterType>[]
    defaultVisibleFields: TField[]
  },
) {
  return defineStore(id, () => {
    const { t } = useI18n()

    const visibleFields = shallowRef<TField[]>([...options.defaultVisibleFields])

    const columns = computed<CatalogueColumnDefinition<TField, TFilterType>[]>(() =>
      options.columns.map((col) => ({
        ...col,
        header: t(col.headerKey),
        phoneClass: phoneClassOf(col.phone),
      })),
    )

    const visibleColumns = computed<CatalogueColumnDefinition<TField, TFilterType>[]>(() =>
      columns.value.filter((column) => visibleFields.value.includes(column.field)),
    )

    function setVisibleFields(fields: TField[]): void {
      visibleFields.value = fields
    }

    function reset(): void {
      visibleFields.value = [...options.defaultVisibleFields]
    }

    return {
      columns,
      visibleFields,

      visibleColumns,

      setVisibleFields,
      reset,
    }
  })
}
