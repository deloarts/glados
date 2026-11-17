import { describe, it, expect } from 'vitest'
import { ref } from 'vue'

import { useNumberRangeFilter } from '../useNumberRangeFilter'

describe('useNumberRangeFilter', () => {
  it('reads null while both bounds are empty and a tuple once either is set', () => {
    const min = ref<number | null>(null)
    const max = ref<number | null>(null)
    const range = useNumberRangeFilter(min, max)

    expect(range.value).toBeNull()
    max.value = 10
    expect(range.value).toEqual([null, 10])
  })

  it('writes a tuple into both refs and clears both on null', () => {
    const min = ref<number | null>(null)
    const max = ref<number | null>(null)
    const range = useNumberRangeFilter(min, max)

    range.value = [2, 8]
    expect([min.value, max.value]).toEqual([2, 8])

    range.value = null
    expect([min.value, max.value]).toEqual([null, null])
  })
})
