import { byMainRange } from './sizeRanges'

/**
 * Numeric values of ISO 286-1 (standard tolerance grades, fundamental
 * deviations, Δ) and ISO 286-2 (limit deviations of individual tolerance
 * classes), all in micrometres. Rows follow the ranges in `sizeRanges.ts`.
 */

/**
 * Standard tolerance grades IT1 to IT18, one row per range of
 * `IT_RANGE_UPPER_BOUNDS`, one column per grade starting at IT1.
 */
export const IT_GRADES: readonly (readonly number[])[] = [
  [0.8, 1.2, 2, 3, 4, 6, 10, 14, 25, 40, 60, 100, 140, 250, 400, 600, 1000, 1400],
  [1, 1.5, 2.5, 4, 5, 8, 12, 18, 30, 48, 75, 120, 180, 300, 480, 750, 1200, 1800],
  [1, 1.5, 2.5, 4, 6, 9, 15, 22, 36, 58, 90, 150, 220, 360, 580, 900, 1500, 2200],
  [1.2, 2, 3, 5, 8, 11, 18, 27, 43, 70, 110, 180, 270, 430, 700, 1100, 1800, 2700],
  [1.5, 2.5, 4, 6, 9, 13, 21, 33, 52, 84, 130, 210, 330, 520, 840, 1300, 2100, 3300],
  [1.5, 2.5, 4, 7, 11, 16, 25, 39, 62, 100, 160, 250, 390, 620, 1000, 1600, 2500, 3900],
  [2, 3, 5, 8, 13, 19, 30, 46, 74, 120, 190, 300, 460, 740, 1200, 1900, 3000, 4600],
  [2.5, 4, 6, 10, 15, 22, 35, 54, 87, 140, 220, 350, 540, 870, 1400, 2200, 3500, 5400],
  [3.5, 5, 8, 12, 18, 25, 40, 63, 100, 160, 250, 400, 630, 1000, 1600, 2500, 4000, 6300],
  [4.5, 7, 10, 14, 20, 29, 46, 72, 115, 185, 290, 460, 720, 1150, 1850, 2900, 4600, 7200],
  [6, 8, 12, 16, 23, 32, 52, 81, 130, 210, 320, 520, 810, 1300, 2100, 3200, 5200, 8100],
  [7, 9, 13, 18, 25, 36, 57, 89, 140, 230, 360, 570, 890, 1400, 2300, 3600, 5700, 8900],
  [8, 10, 15, 20, 27, 40, 63, 97, 155, 250, 400, 630, 970, 1550, 2500, 4000, 6300, 9700],
  [9, 11, 16, 22, 32, 44, 70, 110, 175, 280, 440, 700, 1100, 1750, 2800, 4400, 7000, 11000],
  [10, 13, 18, 25, 36, 50, 80, 125, 200, 320, 500, 800, 1250, 2000, 3200, 5000, 8000, 12500],
  [11, 15, 21, 28, 40, 56, 90, 140, 230, 360, 560, 900, 1400, 2300, 3600, 5600, 9000, 14000],
  [13, 18, 24, 33, 47, 66, 105, 165, 260, 420, 660, 1050, 1650, 2600, 4200, 6600, 10500, 16500],
  [15, 21, 29, 39, 55, 78, 125, 195, 310, 500, 780, 1250, 1950, 3100, 5000, 7800, 12500, 19500],
  [18, 25, 35, 46, 65, 92, 150, 230, 370, 600, 920, 1500, 2300, 3700, 6000, 9200, 15000, 23000],
  [22, 30, 41, 55, 78, 110, 175, 280, 440, 700, 1100, 1750, 2800, 4400, 7000, 11000, 17500, 28000],
  [26, 36, 50, 68, 96, 135, 210, 330, 540, 860, 1350, 2100, 3300, 5400, 8600, 13500, 21000, 33000],
]

export const MIN_GRADE = 1
export const MAX_GRADE = 18

/**
 * Δ added to the upper deviation of the hole letters K, M, N (up to IT8) and
 * P, R, S (up to IT7). Keyed by grade, one value per main range; the first
 * range (up to 3 mm) has no Δ.
 */
export const DELTA: Readonly<Record<number, readonly number[]>> = {
  3: [0, 1, 1, 1, 1.5, 1.5, 2, 2, 3, 3, 4, 4, 5],
  4: [0, 1.5, 1.5, 2, 2, 3, 3, 4, 4, 4, 4, 5, 5],
  5: [0, 1, 2, 3, 3, 4, 5, 5, 6, 6, 7, 7, 7],
  6: [0, 3, 3, 3, 4, 5, 6, 7, 7, 9, 9, 11, 13],
  7: [0, 4, 6, 7, 8, 9, 11, 13, 15, 17, 20, 21, 23],
  8: [0, 6, 7, 9, 12, 14, 16, 19, 23, 26, 29, 32, 34],
}

/** A grade span, both ends included. */
export type GradeSpan = readonly [number, number]

/**
 * How a letter's two limit deviations follow from its table value and the IT
 * value of the chosen grade.
 *
 * - `upper`: the table holds the upper deviation, the lower one is upper − IT.
 *   `deltaUpTo` adds Δ to the table value for grades up to that grade.
 * - `lower`: the table holds the lower deviation, the upper one is lower + IT.
 * - `shaftK`: shaft k, whose lower deviation is the table value for IT4 to IT7
 *   and zero for every other grade.
 * - `symmetric`: js and JS, ±IT/2.
 * - `zero`: h (upper deviation 0) and H (lower deviation 0), defined for every
 *   size the IT table covers.
 */
export type DeviationRule =
  | { kind: 'upper'; values: readonly number[]; grades: GradeSpan; deltaUpTo?: number }
  | { kind: 'lower'; values: readonly number[]; grades: GradeSpan }
  | { kind: 'shaftK'; values: readonly number[]; grades: GradeSpan }
  | { kind: 'symmetric'; grades: GradeSpan }
  | { kind: 'zero'; bound: 'upper' | 'lower'; grades: GradeSpan }

/**
 * Shaft fundamental deviations, one value per fine deviation range. The grade
 * span is the intersection of the grades the standard defines for the letter
 * and the grades the table value applies to.
 */
export const SHAFT_RULES: Readonly<Record<string, DeviationRule>> = {
  a: {
    kind: 'upper',
    grades: [9, 13],
    values: [
      -270, -270, -280, -290, -290, -300, -300, -310, -320, -340, -360, -380, -410, -460, -520,
      -580, -660, -740, -820, -920, -1050, -1200, -1350, -1500, -1650,
    ],
  },
  c: {
    kind: 'upper',
    grades: [8, 12],
    values: [
      -60, -70, -80, -95, -95, -110, -110, -120, -130, -140, -150, -170, -180, -200, -210, -230,
      -240, -260, -280, -300, -330, -360, -400, -440, -480,
    ],
  },
  d: {
    kind: 'upper',
    grades: [5, 13],
    values: byMainRange([-20, -30, -40, -50, -65, -80, -100, -120, -145, -170, -190, -210, -230]),
  },
  e: {
    kind: 'upper',
    grades: [5, 10],
    values: byMainRange([-14, -20, -25, -32, -40, -50, -60, -72, -85, -100, -110, -125, -135]),
  },
  f: {
    kind: 'upper',
    grades: [3, 10],
    values: byMainRange([-6, -10, -13, -16, -20, -25, -30, -36, -43, -50, -56, -62, -68]),
  },
  g: {
    kind: 'upper',
    grades: [3, 10],
    values: byMainRange([-2, -4, -5, -6, -7, -9, -10, -12, -14, -15, -17, -18, -20]),
  },
  h: { kind: 'zero', bound: 'upper', grades: [1, 18] },
  js: { kind: 'symmetric', grades: [1, 18] },
  // The table value of j applies to j7 only; j5 and j6 are explicit classes.
  j: {
    kind: 'lower',
    grades: [7, 7],
    values: byMainRange([-4, -4, -5, -6, -8, -10, -12, -15, -18, -21, -26, -28, -32]),
  },
  k: {
    kind: 'shaftK',
    grades: [4, 13],
    values: byMainRange([0, 1, 1, 1, 2, 2, 2, 3, 3, 4, 4, 4, 5]),
  },
  m: {
    kind: 'lower',
    grades: [3, 9],
    values: byMainRange([2, 4, 6, 7, 8, 9, 11, 13, 15, 17, 20, 21, 23]),
  },
  n: {
    kind: 'lower',
    grades: [3, 9],
    values: byMainRange([4, 8, 10, 12, 15, 17, 20, 23, 27, 31, 34, 37, 40]),
  },
  p: {
    kind: 'lower',
    grades: [3, 10],
    values: byMainRange([6, 12, 15, 18, 22, 26, 32, 37, 43, 50, 56, 62, 68]),
  },
  r: {
    kind: 'lower',
    grades: [3, 10],
    values: [
      10, 15, 19, 23, 23, 28, 28, 34, 34, 41, 43, 51, 54, 63, 65, 68, 77, 80, 84, 94, 98, 108, 114,
      126, 132,
    ],
  },
  s: {
    kind: 'lower',
    grades: [3, 10],
    values: [
      14, 19, 23, 28, 28, 35, 35, 43, 43, 53, 59, 71, 79, 92, 100, 108, 122, 130, 140, 158, 170, 190,
      208, 232, 252,
    ],
  },
}

/** Hole fundamental deviations, one value per fine deviation range. */
export const HOLE_RULES: Readonly<Record<string, DeviationRule>> = {
  A: {
    kind: 'lower',
    grades: [9, 13],
    values: [
      270, 270, 280, 290, 290, 300, 300, 310, 320, 340, 360, 380, 410, 460, 520, 580, 660, 740, 820,
      920, 1050, 1200, 1350, 1500, 1650,
    ],
  },
  C: {
    kind: 'lower',
    grades: [8, 13],
    values: [
      60, 70, 80, 95, 95, 110, 110, 120, 130, 140, 150, 170, 180, 200, 210, 230, 240, 260, 280, 300,
      330, 360, 400, 440, 480,
    ],
  },
  D: {
    kind: 'lower',
    grades: [6, 13],
    values: byMainRange([20, 30, 40, 50, 65, 80, 100, 120, 145, 170, 190, 210, 230]),
  },
  E: {
    kind: 'lower',
    grades: [5, 10],
    values: byMainRange([14, 20, 25, 32, 40, 50, 60, 72, 85, 100, 110, 125, 135]),
  },
  F: {
    kind: 'lower',
    grades: [3, 10],
    values: byMainRange([6, 10, 13, 16, 20, 25, 30, 36, 43, 50, 56, 62, 68]),
  },
  G: {
    kind: 'lower',
    grades: [3, 10],
    values: byMainRange([2, 4, 5, 6, 7, 9, 10, 12, 14, 15, 17, 18, 20]),
  },
  H: { kind: 'zero', bound: 'lower', grades: [1, 18] },
  JS: { kind: 'symmetric', grades: [1, 18] },
  // The table value of J applies to J8 only; J6 and J7 are explicit classes.
  J: {
    kind: 'upper',
    grades: [8, 8],
    values: byMainRange([6, 10, 12, 15, 20, 24, 28, 34, 41, 47, 55, 60, 66]),
  },
  K: {
    kind: 'upper',
    grades: [3, 8],
    deltaUpTo: 8,
    values: byMainRange([0, -1, -1, -1, -2, -2, -2, -3, -3, -4, -4, -4, -5]),
  },
  M: {
    kind: 'upper',
    grades: [3, 8],
    deltaUpTo: 8,
    values: byMainRange([-2, -4, -6, -7, -8, -9, -11, -13, -15, -17, -20, -21, -23]),
  },
  N: {
    kind: 'upper',
    grades: [3, 8],
    deltaUpTo: 8,
    values: byMainRange([-4, -8, -10, -12, -15, -17, -20, -23, -27, -31, -34, -37, -40]),
  },
  P: {
    kind: 'upper',
    grades: [3, 10],
    deltaUpTo: 7,
    values: byMainRange([-6, -12, -15, -18, -22, -26, -32, -37, -43, -50, -56, -62, -68]),
  },
  R: {
    kind: 'upper',
    grades: [3, 10],
    deltaUpTo: 7,
    values: [
      -10, -15, -19, -23, -23, -28, -28, -34, -34, -41, -43, -51, -54, -63, -65, -68, -77, -80, -84,
      -94, -98, -108, -114, -126, -132,
    ],
  },
  S: {
    kind: 'upper',
    grades: [3, 10],
    deltaUpTo: 7,
    values: [
      -14, -19, -23, -28, -28, -35, -35, -43, -43, -53, -59, -71, -79, -92, -100, -108, -122, -130,
      -140, -158, -170, -190, -208, -232, -252,
    ],
  },
}

/** Upper and lower deviation of one tolerance class at one size, in µm. */
export type LimitPair = readonly [upper: number, lower: number]

export interface ExplicitClass {
  /** One pair per fine deviation range. */
  limits: readonly LimitPair[]
  /** The class is not defined for nominal sizes up to and including this size. */
  notUpTo?: number
}

/**
 * Tolerance classes whose limits ISO 286-2 lists directly although the general
 * rule above does not cover them (j5, j6, J6, J7, N9, u8, x8), plus M6, which
 * has a special case the rule cannot express.
 */
export const EXPLICIT_CLASSES: Readonly<Record<string, ExplicitClass>> = {
  j5: {
    limits: byMainRange<LimitPair>([
      [2, -2], [3, -2], [4, -2], [5, -3], [5, -4], [6, -5], [6, -7], [6, -9], [7, -11], [7, -13],
      [7, -16], [7, -18], [7, -20],
    ]),
  },
  j6: {
    limits: byMainRange<LimitPair>([
      [4, -2], [6, -2], [7, -2], [8, -3], [9, -4], [11, -5], [12, -7], [13, -9], [14, -11],
      [16, -13], [16, -16], [18, -18], [20, -20],
    ]),
  },
  J6: {
    limits: byMainRange<LimitPair>([
      [2, -4], [5, -3], [5, -4], [6, -5], [8, -5], [10, -6], [13, -6], [16, -6], [18, -7],
      [22, -7], [25, -7], [29, -7], [33, -7],
    ]),
  },
  J7: {
    limits: byMainRange<LimitPair>([
      [4, -6], [6, -6], [8, -7], [10, -8], [12, -9], [14, -11], [18, -12], [22, -13], [26, -14],
      [30, -16], [36, -16], [39, -18], [43, -20],
    ]),
  },
  // The general rule gives M6 an upper deviation of -11 µm from 250 to 315 mm;
  // the standard sets -9 µm there as a special case, so M6 is listed in full.
  M6: {
    limits: byMainRange<LimitPair>([
      [-2, -8], [-1, -9], [-3, -12], [-4, -15], [-4, -17], [-4, -20], [-5, -24], [-6, -28],
      [-8, -33], [-8, -37], [-9, -41], [-10, -46], [-10, -50],
    ]),
  },
  N9: {
    notUpTo: 1,
    limits: byMainRange<LimitPair>([
      [-4, -29], [0, -30], [0, -36], [0, -43], [0, -52], [0, -62], [0, -74], [0, -87], [0, -100],
      [0, -115], [0, -130], [0, -140], [0, -155],
    ]),
  },
  u8: {
    limits: [
      [32, 18], [41, 23], [50, 28], [60, 33], [60, 33], [74, 41], [81, 48], [99, 60], [109, 70],
      [133, 87], [148, 102], [178, 124], [198, 144], [233, 170], [253, 190], [273, 210],
      [308, 236], [330, 258], [356, 284], [396, 315], [431, 350], [479, 390], [524, 435],
      [587, 490], [637, 540],
    ],
  },
  x8: {
    limits: [
      [34, 20], [46, 28], [56, 34], [67, 40], [72, 45], [87, 54], [97, 64], [119, 80], [136, 97],
      [168, 122], [192, 146], [232, 178], [264, 210], [311, 248], [343, 280], [373, 310],
      [422, 350], [457, 385], [497, 425], [556, 475], [606, 525], [679, 590], [749, 660],
      [837, 740], [917, 820],
    ],
  },
}
