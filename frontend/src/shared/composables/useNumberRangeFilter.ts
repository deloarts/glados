import { computed, type Ref, type WritableComputedRef } from 'vue'

type NumberRange = [number | null, number | null] | null

/**
 * Binds a `[min, max]` range input, such as `NumberRangeRowFilter`, to two
 * separate store refs, the numeric counterpart of `useDateRangeFilter`. A
 * store keeps the bounds apart because each one becomes its own request
 * param; the input wants a single value it can clear as a whole.
 */
export function useNumberRangeFilter(
  minRef: Ref<number | null>,
  maxRef: Ref<number | null>,
): WritableComputedRef<NumberRange> {
  return computed({
    get: (): NumberRange =>
      minRef.value === null && maxRef.value === null ? null : [minRef.value, maxRef.value],
    set: (value: NumberRange) => {
      minRef.value = value?.[0] ?? null
      maxRef.value = value?.[1] ?? null
    },
  })
}
