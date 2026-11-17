import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'

import {
  useDateRangeFilter,
  useDateRangeTupleFilter,
  useKeyedDateRangeFilter,
} from '../useDateRangeFilter'
import type { DateRangeTuple } from '../useDateRangeFilter'

describe('useDateRangeFilter', () => {
  it('reads null while `from` is unset, regardless of `to`', () => {
    const from = ref<Date | null>(null)
    const to = ref<Date | null>(new Date('2026-02-01'))

    const range = useDateRangeFilter(from, to)

    expect(range.value).toBeNull()
  })

  it('reads a [from, to] tuple once `from` is set', () => {
    const fromDate = new Date('2026-01-01')
    const toDate = new Date('2026-01-31')
    const from = ref<Date | null>(fromDate)
    const to = ref<Date | null>(toDate)

    const range = useDateRangeFilter(from, to)

    expect(range.value).toEqual([fromDate, toDate])
  })

  it('assigning a two-element array splits it across both refs', () => {
    const from = ref<Date | null>(null)
    const to = ref<Date | null>(null)
    const range = useDateRangeFilter(from, to)
    const fromDate = new Date('2026-03-01')
    const toDate = new Date('2026-03-15')

    range.value = [fromDate, toDate]

    expect(from.value).toBe(fromDate)
    expect(to.value).toBe(toDate)
  })

  it('assigning an in-progress range ([from, null]) leaves `to` null', () => {
    const from = ref<Date | null>(null)
    const to = ref<Date | null>(null)
    const range = useDateRangeFilter(from, to)
    const fromDate = new Date('2026-03-01')

    range.value = [fromDate, null]

    expect(from.value).toBe(fromDate)
    expect(to.value).toBeNull()
  })

  it('assigning null clears both refs', () => {
    const from = ref<Date | null>(new Date('2026-01-01'))
    const to = ref<Date | null>(new Date('2026-01-31'))
    const range = useDateRangeFilter(from, to)

    range.value = null

    expect(from.value).toBeNull()
    expect(to.value).toBeNull()
  })

  it('assigning undefined (DatePicker clear) clears both refs', () => {
    const from = ref<Date | null>(new Date('2026-01-01'))
    const to = ref<Date | null>(new Date('2026-01-31'))
    const range = useDateRangeFilter(from, to)

    range.value = undefined

    expect(from.value).toBeNull()
    expect(to.value).toBeNull()
  })

  it('assigning a bare Date treats it as `from` with no `to`', () => {
    const from = ref<Date | null>(null)
    const to = ref<Date | null>(new Date('2026-01-31'))
    const range = useDateRangeFilter(from, to)
    const fromDate = new Date('2026-04-01')

    range.value = fromDate

    expect(from.value).toBe(fromDate)
    expect(to.value).toBeNull()
  })
})

describe('useDateRangeTupleFilter', () => {
  it('reads null while `from` is unset and a pair once it is set', () => {
    const fromDate = new Date('2026-01-01')
    const range = ref<DateRangeTuple>([null, new Date('2026-01-31')])
    const { getDateRangeModel } = useDateRangeTupleFilter(range)

    expect(getDateRangeModel()).toBeNull()

    range.value = [fromDate, null]
    expect(getDateRangeModel()).toEqual([fromDate, null])
  })

  it('writes a new pair for every emitted shape and calls onChange', () => {
    const onChange = vi.fn<() => void>()
    const range = ref<DateRangeTuple>([null, null])
    const { setDateRangeModel } = useDateRangeTupleFilter(range, onChange)
    const fromDate = new Date('2026-03-01')
    const toDate = new Date('2026-03-15')

    setDateRangeModel([fromDate, toDate])
    expect(range.value).toEqual([fromDate, toDate])

    setDateRangeModel(fromDate)
    expect(range.value).toEqual([fromDate, null])

    setDateRangeModel(null)
    expect(range.value).toEqual([null, null])
    expect(onChange).toHaveBeenCalledTimes(3)
  })
})

describe('useKeyedDateRangeFilter', () => {
  it('reads a field without an entry as an empty range', () => {
    const ranges = ref<Record<string, DateRangeTuple>>({})
    const { getDateRangeModel } = useKeyedDateRangeFilter(ranges)

    expect(getDateRangeModel('created')).toBeNull()
  })

  it('writes the pair of one field and calls onChange', () => {
    const onChange = vi.fn<() => void>()
    const otherFrom = new Date('2026-01-01')
    const ranges = ref<Record<string, DateRangeTuple>>({ modified: [otherFrom, null] })
    const { getDateRangeModel, setDateRangeModel } = useKeyedDateRangeFilter(ranges, onChange)
    const fromDate = new Date('2026-03-01')

    setDateRangeModel('created', [fromDate, null])

    expect(ranges.value.created).toEqual([fromDate, null])
    expect(ranges.value.modified).toEqual([otherFrom, null])
    expect(getDateRangeModel('created')).toEqual([fromDate, null])
    expect(onChange).toHaveBeenCalledTimes(1)

    setDateRangeModel('created', undefined)
    expect(ranges.value.created).toEqual([null, null])
  })
})
