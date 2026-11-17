import { computed, type Ref, type WritableComputedRef } from 'vue'

/**
 * What OpenVue's `DatePicker` (`selectionMode="range"`) round-trips through
 * `modelValue`/`update:modelValue`: a two-element array while a range is
 * being picked or already set, a bare `Date` if some caller ever passes a
 * single value, or `null`/`undefined` on clear.
 */
type DateRangeInput = Date | Array<Date | null> | null | undefined

/**
 * The get/set pair every filterable date-range column repeats: read a
 * `[from, to]` tuple (or `null` once `from` itself is unset) for the
 * DatePicker's `modelValue`, and on `update:modelValue`/`clear-click`,
 * normalize whatever shape it emits back into the two underlying refs.
 * Returned as a `WritableComputedRef` so a column needs only
 * `v-model="range"` instead of a hand-rolled getter function plus setter
 * function pair.
 */
export function useDateRangeFilter(
  fromRef: Ref<Date | null>,
  toRef: Ref<Date | null>,
): WritableComputedRef<[Date, Date | null] | null, DateRangeInput> {
  return computed({
    get: () => (fromRef.value ? ([fromRef.value, toRef.value] as [Date, Date | null]) : null),
    set: (value) => {
      const [from, to] = Array.isArray(value) ? value : [value ?? null, null]
      fromRef.value = from ?? null
      toRef.value = to ?? null
    },
  })
}

/** A date range held as one `[from, to]` pair, as some filter stores keep it. */
export type DateRangeTuple = [Date | null, Date | null]

/**
 * The DatePicker model of a stored pair. OpenVue's range DatePicker crashes
 * on a `[null, null]` model, so an empty range reads as `null`.
 */
function toDateRangeModel([from, to]: DateRangeTuple): [Date, Date | null] | null {
  return from ? [from, to] : null
}

/** Whatever shape the DatePicker emits, normalized to a stored pair. */
function toDateRangeTuple(value: DateRangeInput): DateRangeTuple {
  const [from, to] = Array.isArray(value) ? value : [value ?? null, null]
  return [from ?? null, to ?? null]
}

/**
 * The DatePicker model of a date range kept as one `[from, to]` ref. Every
 * set writes a new pair, so a watcher on the ref sees the change, and then
 * calls `onChange`, which a server-side table uses to refetch. The getter
 * builds a new model on each call; wrap it in `computed` where the model
 * should keep its identity between renders.
 */
export function useDateRangeTupleFilter(range: Ref<DateRangeTuple>, onChange?: () => void) {
  function getDateRangeModel(): [Date, Date | null] | null {
    return toDateRangeModel(range.value)
  }

  function setDateRangeModel(value: DateRangeInput): void {
    range.value = toDateRangeTuple(value)
    onChange?.()
  }

  return { getDateRangeModel, setDateRangeModel }
}

/**
 * The DatePicker models of several date-range columns kept in one record of
 * `[from, to]` pairs keyed by field name, as the catalogue filter stores
 * hold them. A field without an entry reads as an empty range. Every set
 * writes a new pair for that field and then calls `onChange`.
 */
export function useKeyedDateRangeFilter(
  ranges: Ref<Record<string, DateRangeTuple>>,
  onChange?: () => void,
) {
  function getDateRangeModel(field: string): [Date, Date | null] | null {
    return toDateRangeModel(ranges.value[field] ?? [null, null])
  }

  function setDateRangeModel(field: string, value: DateRangeInput): void {
    ranges.value[field] = toDateRangeTuple(value)
    onChange?.()
  }

  return { getDateRangeModel, setDateRangeModel }
}
