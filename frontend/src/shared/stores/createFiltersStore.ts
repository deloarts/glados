import { computed, ref } from 'vue'
import type { ComputedRef, Ref } from 'vue'
import { defineStore } from 'pinia'

/** The sort state every sortable filters store uses. */
export type FilterSortDir = 'asc' | 'desc'

type SortBundle<TSortField extends string> = {
  sortBy: Ref<TSortField | null>
  sortDir: Ref<FilterSortDir>
  setSort: (field: TSortField, dir: FilterSortDir) => void
  clearSort: () => void
}

/**
 * The generic bundle of a filters store: one ref per field, `clearTrigger`,
 * `hasActiveFilters` and `clearAll()`. The literal `TSortable` makes the sort
 * members required on sortable stores instead of optional everywhere.
 */
export type FiltersStoreBase<
  TFields extends Record<string, unknown>,
  TSortField extends string,
  TSortable extends boolean = false,
> = {
  [K in keyof TFields]: Ref<TFields[K]>
} & {
  clearTrigger: Ref<number>
  hasActiveFilters: ComputedRef<boolean>
  clearAll: () => void
} & (TSortable extends true ? SortBundle<TSortField> : Record<never, never>)

export interface FiltersStoreExtension<TExtra extends Record<string, unknown>> {
  /** Store-specific extras merged onto the public surface. */
  state: TExtra
  /**
   * Runs in `clearAll()` before `clearTrigger` bumps, so extras reset too
   * without counting toward `hasActiveFilters`.
   */
  onClear?: () => void
}

export interface CreateFiltersStoreConfig<
  TFields extends Record<string, unknown>,
  TSortField extends string,
  TSortable extends boolean,
  TExtra extends Record<string, unknown>,
> {
  /**
   * Field defaults, also what `clearAll()` restores. Use a factory when a
   * consumer mutates a default in place, or resets would share the mutated
   * object.
   */
  defaults: TFields | (() => TFields)
  /**
   * Overrides the default reference comparison, for example so an empty
   * array counts as inactive.
   */
  isActive?: (fields: TFields) => boolean
  /**
   * Required and kept in sync with `TSortable`; sorting starts unsorted
   * ascending.
   */
  sortable: TSortable
  /**
   * Builds store-specific state inside the store's `setup()`. Pass its
   * shape explicitly as `TExtra`, because inference through this callback
   * falls back to an empty type.
   */
  extend?: (base: FiltersStoreBase<TFields, TSortField, TSortable>) => FiltersStoreExtension<TExtra>
}

type FiltersStoreReturn<
  TFields extends Record<string, unknown>,
  TSortField extends string,
  TSortable extends boolean,
  TExtra extends Record<string, unknown>,
> = FiltersStoreBase<TFields, TSortField, TSortable> & TExtra

/**
 * Builds a filters store: filter fields, `clearTrigger`, `hasActiveFilters`,
 * `clearAll()` and optionally sorting. Anything else is wired in through
 * `extend`.
 *
 * Give every generic explicitly: an inferred `TSortable` widens to boolean
 * and an inferred `TExtra` falls back to empty. The setup function is
 * annotated with its return type for the same reason.
 */
export function createFiltersStore<
  TFields extends Record<string, unknown>,
  TSortField extends string = never,
  TSortable extends boolean = false,
  TExtra extends Record<string, unknown> = Record<never, never>,
>(id: string, config: CreateFiltersStoreConfig<TFields, TSortField, TSortable, TExtra>) {
  return defineStore(id, (): FiltersStoreReturn<TFields, TSortField, TSortable, TExtra> => {
    const resolveDefaults = (): TFields =>
      typeof config.defaults === 'function'
        ? (config.defaults as () => TFields)()
        : ({ ...config.defaults } as TFields)

    const initialDefaults = resolveDefaults()
    const fields = {} as { [K in keyof TFields]: Ref<TFields[K]> }
    for (const key of Object.keys(initialDefaults) as (keyof TFields)[]) {
      fields[key] = ref(initialDefaults[key]) as Ref<TFields[typeof key]>
    }

    const clearTrigger = ref(0)

    const sortRefs = config.sortable
      ? {
          sortBy: ref<TSortField | null>(null) as Ref<TSortField | null>,
          sortDir: ref<FilterSortDir>('asc'),
        }
      : null

    const currentFields = (): TFields => {
      const out = {} as TFields
      for (const key of Object.keys(fields) as (keyof TFields)[]) {
        out[key] = fields[key].value
      }
      return out
    }

    const defaultIsActive = (values: TFields): boolean =>
      (Object.keys(values) as (keyof TFields)[]).some((key) => values[key] !== initialDefaults[key])

    const hasActiveFilters = computed<boolean>(() =>
      (config.isActive ?? defaultIsActive)(currentFields()),
    )

    function setSort(field: TSortField, dir: FilterSortDir): void {
      if (!sortRefs) return
      sortRefs.sortBy.value = field
      sortRefs.sortDir.value = dir
    }

    function clearSort(): void {
      if (!sortRefs) return
      sortRefs.sortBy.value = null
      sortRefs.sortDir.value = 'asc'
    }

    // Declared after clearAll but only read when it is called, by which time
    // it exists.
    function clearAll(): void {
      const fresh = resolveDefaults()
      for (const key of Object.keys(fields) as (keyof TFields)[]) {
        fields[key].value = fresh[key]
      }
      clearSort()
      onClear?.()
      clearTrigger.value++
    }

    const base = {
      ...fields,
      clearTrigger,
      hasActiveFilters,
      clearAll,
      ...(sortRefs
        ? { sortBy: sortRefs.sortBy, sortDir: sortRefs.sortDir, setSort, clearSort }
        : {}),
    } as FiltersStoreBase<TFields, TSortField, TSortable>

    const extension = config.extend?.(base)
    const onClear = extension?.onClear

    return { ...base, ...(extension?.state ?? ({} as TExtra)) } as FiltersStoreReturn<
      TFields,
      TSortField,
      TSortable,
      TExtra
    >
  })
}
