/**
 * Metric ISO threads (ISO 261, ISO 724, DIN 13). Only nominal diameter and
 * pitch are stored; every other dimension follows from the basic profile
 * formulas of ISO 724. All lengths in mm.
 */

export interface MetricThread {
  /** Designation key used in links: "M8" for a coarse thread, "M8x1" for a fine one. */
  code: string
  d: number
  pitch: number
  fine: boolean
}

/** Coarse pitch threads: series 1 first, then the series 2 sizes up to M68. */
const COARSE: readonly (readonly [d: number, pitch: number])[] = [
  [1, 0.25], [1.2, 0.25], [1.6, 0.35], [2, 0.4], [2.5, 0.45], [3, 0.5], [4, 0.7], [5, 0.8],
  [6, 1], [7, 1], [8, 1.25], [10, 1.5], [12, 1.75], [14, 2], [16, 2], [18, 2.5], [20, 2.5],
  [22, 2.5], [24, 3], [27, 3], [30, 3.5], [33, 3.5], [36, 4], [39, 4], [42, 4.5], [45, 4.5],
  [48, 5], [52, 5], [56, 5.5], [60, 5.5], [64, 6], [68, 6],
]

/** Fine pitch threads in common use. */
const FINE: readonly (readonly [d: number, pitch: number])[] = [
  [2, 0.25], [3, 0.25], [4, 0.2], [4, 0.35], [5, 0.25], [5, 0.5], [6, 0.25], [6, 0.5],
  [6, 0.75], [8, 0.25], [8, 0.5], [8, 1], [10, 0.25], [10, 0.5], [10, 1], [12, 0.35],
  [12, 0.5], [12, 1], [12, 1.5], [16, 0.5], [16, 1], [16, 1.5], [20, 1], [20, 1.5], [24, 1.5],
  [24, 2], [30, 1.5], [30, 2], [36, 1.5], [36, 2], [36, 3], [42, 1.5], [42, 2], [48, 1.5],
  [48, 2], [56, 1.5], [56, 2], [64, 2],
]

/** Width across flats of hexagon heads (ISO 272), by nominal diameter. */
export const WIDTH_ACROSS_FLATS: Readonly<Record<number, number>> = {
  1.6: 3.2, 2: 4, 2.5: 5, 3: 5.5, 4: 7, 5: 8, 6: 10, 8: 13, 10: 16, 12: 18, 16: 24, 20: 30,
  24: 36, 30: 46, 36: 55, 42: 65, 48: 75, 56: 85, 64: 95,
}

function fmtNumber(value: number): string {
  return String(value)
}

export const COARSE_THREADS: readonly MetricThread[] = COARSE.map(([d, pitch]) => ({
  code: `M${fmtNumber(d)}`,
  d,
  pitch,
  fine: false,
}))

export const FINE_THREADS: readonly MetricThread[] = FINE.map(([d, pitch]) => ({
  code: `M${fmtNumber(d)}x${fmtNumber(pitch)}`,
  d,
  pitch,
  fine: true,
}))

export const ALL_THREADS: readonly MetricThread[] = [...COARSE_THREADS, ...FINE_THREADS]

export function findThread(code: string): MetricThread | undefined {
  return ALL_THREADS.find((thread) => thread.code === code)
}

export interface ThreadGeometry {
  /** Pitch diameter d2 = D2. */
  d2: number
  /** Minor diameter of the external thread. */
  d3: number
  /** Minor diameter of the internal thread. */
  D1: number
  /** Thread depth of the external thread. */
  h3: number
  /** Thread depth of the internal thread. */
  H1: number
  /** Root radius. */
  R: number
  /** Tensile stress area in mm². */
  stressArea: number
  /** Tap drill diameter. */
  tapDrill: number
}

// DIN 336 takes the tap drill as d − P, rounded to a standard drill size where
// that difference falls between two: M8 and M12 are the two coarse threads
// this affects.
const COARSE_TAP_DRILL_OVERRIDES: Readonly<Record<number, number>> = { 8: 6.8, 12: 10.2 }

/**
 * Basic profile dimensions per ISO 724, unrounded. DIN 13 lists them rounded to
 * three decimals.
 */
export function threadGeometry(d: number, pitch: number, fine = false): ThreadGeometry {
  const d2 = d - 0.649519 * pitch
  const d3 = d - 1.226869 * pitch
  return {
    d2,
    d3,
    D1: d - 1.082532 * pitch,
    h3: 0.613435 * pitch,
    H1: 0.541266 * pitch,
    R: 0.144338 * pitch,
    stressArea: (Math.PI / 4) * ((d2 + d3) / 2) ** 2,
    tapDrill: (!fine && COARSE_TAP_DRILL_OVERRIDES[d]) || Math.round((d - pitch) * 1000) / 1000,
  }
}
