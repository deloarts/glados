import { describe, it, expect } from 'vitest'

import { COARSE_THREADS, FINE_THREADS, findThread, threadGeometry } from '../metric'
import { CAP_SCREW_COUNTERBORES, CLEARANCE_HOLES, HEX_COUNTERBORES } from '../holes'
import { TIGHTENING, tighteningFor } from '../tightening'
import { LIMITS_6H_6G } from '../tolerances'

const round = (value: number, digits: number) => Math.round(value * 10 ** digits) / 10 ** digits
// DIN 13 lists diameters to three decimals; two-decimal values are rounded half
// up from those, so compare the same way.
const round2From3 = (value: number) => Math.round(round(value, 3) * 100 + 1e-6) / 100

// Basic dimensions of the coarse threads of series 1 per DIN 13-1:
// d, P, d2, d3, D1, h3, H1, R, stress area, tap drill.
const DIN_13_1: readonly (readonly number[])[] = [
  [1, 0.25, 0.84, 0.69, 0.73, 0.15, 0.14, 0.04, 0.46, 0.75],
  [1.2, 0.25, 1.04, 0.89, 0.93, 0.15, 0.14, 0.04, 0.73, 0.95],
  // DIN 13-1 lists d2 = 1.373 for M1.6, which rounds to 1.37.
  [1.6, 0.35, 1.37, 1.17, 1.22, 0.22, 0.19, 0.05, 1.27, 1.25],
  [2, 0.4, 1.74, 1.51, 1.57, 0.25, 0.22, 0.06, 2.07, 1.6],
  [2.5, 0.45, 2.21, 1.95, 2.01, 0.28, 0.24, 0.07, 3.39, 2.05],
  [3, 0.5, 2.68, 2.39, 2.46, 0.31, 0.27, 0.07, 5.03, 2.5],
  [4, 0.7, 3.55, 3.14, 3.24, 0.43, 0.38, 0.1, 8.78, 3.3],
  [5, 0.8, 4.48, 4.02, 4.13, 0.49, 0.43, 0.12, 14.2, 4.2],
  [6, 1, 5.35, 4.77, 4.92, 0.61, 0.54, 0.14, 20.1, 5],
  [8, 1.25, 7.19, 6.47, 6.65, 0.77, 0.68, 0.18, 36.6, 6.8],
  [10, 1.5, 9.03, 8.16, 8.38, 0.92, 0.81, 0.22, 58, 8.5],
  [12, 1.75, 10.86, 9.85, 10.11, 1.07, 0.95, 0.25, 84.3, 10.2],
  [16, 2, 14.7, 13.55, 13.84, 1.23, 1.08, 0.29, 157, 14],
  [20, 2.5, 18.38, 16.93, 17.29, 1.53, 1.35, 0.36, 245, 17.5],
  [24, 3, 22.05, 20.32, 20.75, 1.84, 1.62, 0.43, 353, 21],
  [30, 3.5, 27.73, 25.71, 26.21, 2.15, 1.89, 0.51, 561, 26.5],
  [36, 4, 33.4, 31.09, 31.67, 2.45, 2.17, 0.58, 817, 32],
  [42, 4.5, 39.08, 36.48, 37.13, 2.76, 2.44, 0.65, 1121, 37.5],
  [48, 5, 44.75, 41.87, 42.59, 3.07, 2.71, 0.72, 1473, 43],
  [56, 5.5, 52.43, 49.25, 50.05, 3.37, 2.98, 0.79, 2030, 50.5],
  [64, 6, 60.1, 56.64, 57.51, 3.68, 3.25, 0.87, 2676, 58],
]

// Fine threads per DIN 13-2 to 13-10: d, P, d2, d3, D1.
const DIN_13_FINE: readonly (readonly number[])[] = [
  [2, 0.25, 1.84, 1.69, 1.73], [3, 0.25, 2.84, 2.69, 2.73], [4, 0.2, 3.87, 3.76, 3.78],
  [4, 0.35, 3.77, 3.57, 3.62], [5, 0.25, 4.84, 4.69, 4.73], [5, 0.5, 4.68, 4.39, 4.46],
  [6, 0.25, 5.84, 5.69, 5.73], [6, 0.5, 5.68, 5.39, 5.46], [6, 0.75, 5.51, 5.08, 5.19],
  [8, 0.25, 7.84, 7.69, 7.73], [8, 0.5, 7.68, 7.39, 7.46], [8, 1, 7.35, 6.77, 6.92],
  [10, 0.25, 9.84, 9.69, 9.73], [10, 0.5, 9.68, 9.39, 9.46], [10, 1, 9.35, 8.77, 8.92],
  [12, 0.35, 11.77, 11.57, 11.62], [12, 0.5, 11.68, 11.39, 11.46], [12, 1, 11.35, 10.77, 10.92],
  [16, 0.5, 15.68, 15.39, 15.46], [16, 1, 15.35, 14.77, 14.92], [16, 1.5, 15.03, 14.16, 14.38],
  [20, 1, 19.35, 18.77, 18.92], [20, 1.5, 19.03, 18.16, 18.38], [24, 1.5, 23.03, 22.16, 22.38],
  [24, 2, 22.7, 21.55, 21.84], [30, 1.5, 29.03, 28.16, 28.38], [30, 2, 28.7, 27.55, 27.84],
  [36, 1.5, 35.03, 34.16, 34.38], [36, 2, 34.7, 33.55, 33.84], [42, 1.5, 41.03, 40.16, 40.38],
  [42, 2, 40.7, 39.55, 39.84], [48, 1.5, 47.03, 46.16, 46.38], [48, 2, 46.7, 45.55, 45.84],
  [56, 1.5, 55.03, 54.16, 54.38], [56, 2, 54.7, 53.55, 53.84], [64, 2, 62.7, 61.55, 61.84],
]

// DIN 13-1 rounds the stress area to three significant digits, or four from 1000 mm² up.
function roundStressArea(value: number): number {
  if (value < 10) return round(value, 2)
  if (value < 100) return round(value, 1)
  return Math.round(value)
}

describe('threadGeometry', () => {
  it('reproduces every coarse thread of DIN 13-1 series 1', () => {
    const mismatches: string[] = []
    for (const [d, P, d2, d3, D1, h3, H1, R, S, drill] of DIN_13_1 as number[][]) {
      const g = threadGeometry(d as number, P as number)
      const actual = [
        round2From3(g.d2), round2From3(g.d3), round2From3(g.D1), round2From3(g.h3),
        round2From3(g.H1), round2From3(g.R), roundStressArea(g.stressArea), g.tapDrill,
      ]
      const expected = [d2, d3, D1, h3, H1, R, S, drill]
      if (JSON.stringify(actual) !== JSON.stringify(expected)) {
        mismatches.push(`M${d}: expected ${expected.join('/')}, got ${actual.join('/')}`)
      }
    }
    expect(mismatches).toEqual([])
  })

  it('reproduces every fine thread of DIN 13', () => {
    const mismatches: string[] = []
    for (const [d, P, d2, d3, D1] of DIN_13_FINE as number[][]) {
      const g = threadGeometry(d as number, P as number, true)
      const actual = [round2From3(g.d2), round2From3(g.d3), round2From3(g.D1)]
      if (JSON.stringify(actual) !== JSON.stringify([d2, d3, D1])) {
        mismatches.push(`M${d}x${P}: expected ${[d2, d3, D1].join('/')}, got ${actual.join('/')}`)
      }
    }
    expect(mismatches).toEqual([])
  })

  it('lists every DIN 13 thread in the selection', () => {
    for (const [d, P] of DIN_13_1 as number[][]) {
      expect(COARSE_THREADS.some((t) => t.d === d && t.pitch === P)).toBe(true)
    }
    for (const [d, P] of DIN_13_FINE as number[][]) {
      expect(FINE_THREADS.some((t) => t.d === d && t.pitch === P)).toBe(true)
    }
  })

  it('takes fine thread tap drills as d − P', () => {
    expect(threadGeometry(8, 1, true).tapDrill).toBe(7)
    expect(threadGeometry(12, 1.5, true).tapDrill).toBe(10.5)
  })

  it('finds threads by their link code', () => {
    expect(findThread('M8')).toEqual({ code: 'M8', d: 8, pitch: 1.25, fine: false })
    expect(findThread('M12x1.5')).toEqual({ code: 'M12x1.5', d: 12, pitch: 1.5, fine: true })
    expect(findThread('M9')).toBeUndefined()
  })
})

describe('6H/6g limits', () => {
  it('start the internal thread zones at the basic profile', () => {
    for (const [code, limits] of Object.entries(LIMITS_6H_6G)) {
      const thread = findThread(code)
      expect(thread).toBeDefined()
      if (!thread) continue
      const g = threadGeometry(thread.d, thread.pitch)
      expect(limits.internal.Dmin).toBe(thread.d)
      expect(limits.internal.D2[0]).toBeCloseTo(g.d2, 3)
      expect(limits.internal.D1[0]).toBeCloseTo(g.D1, 3)
    }
  })

  it('shift the external diameters of a thread by one common deviation', () => {
    for (const [code, limits] of Object.entries(LIMITS_6H_6G)) {
      const thread = findThread(code)
      if (!thread) continue
      const g = threadGeometry(thread.d, thread.pitch)
      const es = limits.external.d[0] - thread.d
      expect(limits.external.d2[0]).toBeCloseTo(g.d2 + es, 2)
      expect(limits.external.d3[0]).toBeCloseTo(g.d3 + es, 2)
      for (const [max, min] of [limits.external.d, limits.external.d2, limits.external.d3]) {
        expect(max).toBeGreaterThan(min as number)
      }
    }
  })
})

describe('holes and tightening tables', () => {
  it('orders the clearance hole series fine < medium < coarse', () => {
    for (const [d, [fine, medium, coarse]] of Object.entries(CLEARANCE_HOLES)) {
      expect(fine).toBeGreaterThan(Number(d))
      expect(medium).toBeGreaterThanOrEqual(fine)
      expect(coarse).toBeGreaterThan(medium)
    }
  })

  it('uses the medium clearance hole as the counterbore through hole', () => {
    const mismatches: string[] = []
    for (const [d, row] of [...Object.entries(CAP_SCREW_COUNTERBORES), ...Object.entries(HEX_COUNTERBORES)]) {
      const clearance = CLEARANCE_HOLES[Number(d)]
      if (clearance && row.dh !== clearance[1]) mismatches.push(`M${d}: ${row.dh} vs ${clearance[1]}`)
    }
    expect(mismatches).toEqual([])
  })

  it('grows torque and preload with the property class', () => {
    for (const row of TIGHTENING) {
      expect(row.torque[1]).toBeGreaterThan(row.torque[0])
      expect(row.torque[2]).toBeGreaterThan(row.torque[1])
      expect(row.preload[1]).toBeGreaterThan(row.preload[0])
      expect(row.preload[2]).toBeGreaterThan(row.preload[1])
    }
  })

  it('finds the tightening row of a coarse thread only', () => {
    expect(tighteningFor(8, 1.25)?.torque).toEqual([27.3, 40.1, 46.9])
    expect(tighteningFor(8, 1)).toBeUndefined()
  })
})
