import { afterEach, describe, expect, it } from 'vitest'
import { FilterService } from '@openvue/core/api'

import { setDisplayTimezone } from '@/core/utils/dates'
import {
  RowFilterMatchMode,
  hasActiveRowFilter,
  matchesDateRange,
  matchesNumberRange,
} from '../rowFilterModes'

describe('rowFilterModes', () => {
  afterEach(() => setDisplayTimezone(null))

  it('registers both modes with the OpenVue FilterService on import', () => {
    // The typings leave the registry out, although DataTable reads it directly.
    const registry = (FilterService as unknown as { filters: Record<string, unknown> }).filters
    expect(registry[RowFilterMatchMode.DATE_RANGE]).toBe(matchesDateRange)
    expect(registry[RowFilterMatchMode.NUMBER_RANGE]).toBe(matchesNumberRange)
  })

  it('reports a filter meta as active only when some value is set', () => {
    const idle = {
      a: { value: null, matchMode: 'contains' },
      b: { value: '', matchMode: 'contains' },
      c: { value: [null, null], matchMode: RowFilterMatchMode.NUMBER_RANGE },
      d: { value: [], matchMode: 'in' },
    }
    expect(hasActiveRowFilter(idle)).toBe(false)
    expect(hasActiveRowFilter({ ...idle, c: { ...idle.c, value: [null, 3] } })).toBe(true)
  })

  describe('matchesDateRange', () => {
    const from = new Date(2026, 2, 10)
    const to = new Date(2026, 2, 20)

    it('matches everything while no bound is set', () => {
      expect(matchesDateRange(null, null)).toBe(true)
      expect(matchesDateRange('2026-01-01', [null, null])).toBe(true)
    })

    it('includes both bounds of a calendar date range', () => {
      expect(matchesDateRange('2026-03-10', [from, to])).toBe(true)
      expect(matchesDateRange('2026-03-20', [from, to])).toBe(true)
      expect(matchesDateRange('2026-03-09', [from, to])).toBe(false)
      expect(matchesDateRange('2026-03-21', [from, to])).toBe(false)
    })

    it('leaves the upper side open while only the first day is picked', () => {
      expect(matchesDateRange('2027-01-01', [from, null])).toBe(true)
      expect(matchesDateRange('2026-03-01', from)).toBe(false)
    })

    it('compares an instant by its day in the display timezone', () => {
      setDisplayTimezone('Europe/Vienna')
      // 23:30 UTC on the 20th is already the 21st in Vienna.
      expect(matchesDateRange('2026-03-20T23:30:00Z', [from, to])).toBe(false)
      expect(matchesDateRange('2026-03-20T12:00:00Z', [from, to])).toBe(true)
    })

    it('never matches an empty cell once a bound is set', () => {
      expect(matchesDateRange(null, [from, to])).toBe(false)
    })
  })

  describe('matchesNumberRange', () => {
    it('matches everything while no bound is set', () => {
      expect(matchesNumberRange(null, null)).toBe(true)
      expect(matchesNumberRange(5, [null, null])).toBe(true)
    })

    it('includes both bounds and allows either side open', () => {
      expect(matchesNumberRange(5, [5, 10])).toBe(true)
      expect(matchesNumberRange(10, [5, 10])).toBe(true)
      expect(matchesNumberRange(11, [5, 10])).toBe(false)
      expect(matchesNumberRange(4, [5, null])).toBe(false)
      expect(matchesNumberRange(400, [5, null])).toBe(true)
      expect(matchesNumberRange(3, [null, 2])).toBe(false)
    })

    it('never matches an empty cell once a bound is set', () => {
      expect(matchesNumberRange(null, [0, null])).toBe(false)
    })
  })
})
