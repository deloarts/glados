import { describe, it, expect } from 'vitest'

import { degreesAndMinutes, lookup, rangeIndexOf } from '../lookup'
import {
  ANGULAR,
  BROKEN_EDGES,
  CIRCULAR_RUN_OUT,
  LINEAR,
  PERPENDICULARITY,
  STRAIGHTNESS_FLATNESS,
  SYMMETRY,
} from '../tables'

describe('ISO 2768 lookup', () => {
  it('finds the linear deviation of the common class mK at 25 mm', () => {
    expect(lookup(LINEAR, 'm', 25)).toEqual({ ok: true, value: 0.2, rangeIndex: 2 })
    expect(lookup(BROKEN_EDGES, 'm', 25)).toEqual({ ok: true, value: 1, rangeIndex: 2 })
    expect(lookup(ANGULAR, 'm', 25)).toEqual({ ok: true, value: 30, rangeIndex: 1 })
    expect(lookup(STRAIGHTNESS_FLATNESS, 'K', 25)).toEqual({ ok: true, value: 0.1, rangeIndex: 1 })
    expect(lookup(PERPENDICULARITY, 'K', 25)).toEqual({ ok: true, value: 0.4, rangeIndex: 0 })
    expect(lookup(SYMMETRY, 'K', 25)).toEqual({ ok: true, value: 0.6, rangeIndex: 0 })
    expect(lookup(CIRCULAR_RUN_OUT, 'K', 25)).toEqual({ ok: true, value: 0.2, rangeIndex: 0 })
  })

  it('includes 0.5 mm in the first linear range and each upper bound in its range', () => {
    expect(rangeIndexOf(LINEAR.ranges, 0.5)).toBe(0)
    expect(rangeIndexOf(LINEAR.ranges, 3)).toBe(0)
    expect(rangeIndexOf(LINEAR.ranges, 3.001)).toBe(1)
    expect(rangeIndexOf(LINEAR.ranges, 4000)).toBe(7)
    expect(rangeIndexOf(ANGULAR.ranges, 10)).toBe(0)
    expect(rangeIndexOf(ANGULAR.ranges, 10000)).toBe(4)
  })

  it('reports sizes outside the tables', () => {
    expect(lookup(LINEAR, 'm', 0.4)).toEqual({ ok: false, reason: 'belowRange', rangeIndex: null })
    expect(lookup(LINEAR, 'm', 4001)).toEqual({ ok: false, reason: 'aboveRange', rangeIndex: null })
    expect(lookup(STRAIGHTNESS_FLATNESS, 'H', 3001)).toEqual({
      ok: false,
      reason: 'aboveRange',
      rangeIndex: null,
    })
    expect(lookup(LINEAR, 'm', 0)).toEqual({ ok: false, reason: 'invalidSize', rangeIndex: null })
  })

  it('reports the ranges a class leaves undefined', () => {
    expect(lookup(LINEAR, 'v', 2)).toEqual({ ok: false, reason: 'notDefined', rangeIndex: 0 })
    expect(lookup(LINEAR, 'f', 3000)).toEqual({ ok: false, reason: 'notDefined', rangeIndex: 7 })
    expect(lookup(LINEAR, 'c', 3000)).toEqual({ ok: true, value: 4, rangeIndex: 7 })
  })

  it('keeps every class row as long as its ranges', () => {
    for (const table of [LINEAR, BROKEN_EDGES, ANGULAR]) {
      for (const row of Object.values(table.values)) expect(row).toHaveLength(table.ranges.length)
    }
    for (const table of [STRAIGHTNESS_FLATNESS, PERPENDICULARITY, SYMMETRY, CIRCULAR_RUN_OUT]) {
      for (const row of Object.values(table.values)) expect(row).toHaveLength(table.ranges.length)
    }
  })

  it('splits angular minutes into degrees and minutes', () => {
    expect(degreesAndMinutes(90)).toEqual({ degrees: 1, minutes: 30 })
    expect(degreesAndMinutes(30)).toEqual({ degrees: 0, minutes: 30 })
    expect(degreesAndMinutes(180)).toEqual({ degrees: 3, minutes: 0 })
  })
})
