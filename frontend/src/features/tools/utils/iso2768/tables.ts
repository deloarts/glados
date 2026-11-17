/**
 * Values of ISO 2768-1 (general tolerances for linear and angular dimensions)
 * and ISO 2768-2 (general geometrical tolerances). Lengths are in mm, angles
 * in minutes of arc. `null` marks a range the standard leaves undefined for a
 * class.
 */

export type LinearClass = 'f' | 'm' | 'c' | 'v'
export type GeometricClass = 'H' | 'K' | 'L'

export const LINEAR_CLASSES: readonly LinearClass[] = ['f', 'm', 'c', 'v']
export const GEOMETRIC_CLASSES: readonly GeometricClass[] = ['H', 'K', 'L']

/**
 * A nominal size range "over `from` up to and including `to`". The first range
 * of a linear table starts at and includes its lower bound (0.5 mm); a range
 * without `to` is open upwards.
 */
export interface SizeRange {
  from: number
  to: number | null
  includeFrom?: boolean
}

export interface ToleranceTable<C extends string> {
  ranges: readonly SizeRange[]
  values: Readonly<Record<C, readonly (number | null)[]>>
}

/** Permissible deviations (±) for linear dimensions except broken edges. */
export const LINEAR: ToleranceTable<LinearClass> = {
  ranges: [
    { from: 0.5, to: 3, includeFrom: true },
    { from: 3, to: 6 },
    { from: 6, to: 30 },
    { from: 30, to: 120 },
    { from: 120, to: 400 },
    { from: 400, to: 1000 },
    { from: 1000, to: 2000 },
    { from: 2000, to: 4000 },
  ],
  values: {
    f: [0.05, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, null],
    m: [0.1, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2, 2],
    c: [0.2, 0.3, 0.5, 0.8, 1.2, 2, 3, 4],
    v: [null, 0.5, 1, 1.5, 2.5, 4, 6, 8],
  },
}

/** Permissible deviations (±) for broken edges: outside radii and chamfer heights. */
export const BROKEN_EDGES: ToleranceTable<LinearClass> = {
  ranges: [
    { from: 0.5, to: 3, includeFrom: true },
    { from: 3, to: 6 },
    { from: 6, to: null },
  ],
  values: {
    f: [0.2, 0.5, 1],
    m: [0.2, 0.5, 1],
    c: [0.4, 1, 2],
    v: [0.4, 1, 2],
  },
}

/** Permissible deviations (±) of angular dimensions in minutes, by the length of the shorter leg. */
export const ANGULAR: ToleranceTable<LinearClass> = {
  ranges: [
    { from: 0, to: 10 },
    { from: 10, to: 50 },
    { from: 50, to: 120 },
    { from: 120, to: 400 },
    { from: 400, to: null },
  ],
  values: {
    f: [60, 30, 20, 10, 5],
    m: [60, 30, 20, 10, 5],
    c: [90, 60, 30, 15, 10],
    v: [180, 120, 60, 30, 20],
  },
}

/** General tolerances on straightness and flatness, by nominal length. */
export const STRAIGHTNESS_FLATNESS: ToleranceTable<GeometricClass> = {
  ranges: [
    { from: 0, to: 10 },
    { from: 10, to: 30 },
    { from: 30, to: 100 },
    { from: 100, to: 300 },
    { from: 300, to: 1000 },
    { from: 1000, to: 3000 },
  ],
  values: {
    H: [0.02, 0.05, 0.1, 0.2, 0.3, 0.4],
    K: [0.05, 0.1, 0.2, 0.4, 0.6, 0.8],
    L: [0.1, 0.2, 0.4, 0.8, 1.2, 1.6],
  },
}

/** General tolerances on perpendicularity, by the length of the shorter side. */
export const PERPENDICULARITY: ToleranceTable<GeometricClass> = {
  ranges: [
    { from: 0, to: 100 },
    { from: 100, to: 300 },
    { from: 300, to: 1000 },
    { from: 1000, to: 3000 },
  ],
  values: {
    H: [0.2, 0.3, 0.4, 0.5],
    K: [0.4, 0.6, 0.8, 1],
    L: [0.6, 1, 1.5, 2],
  },
}

/** General tolerances on symmetry, by the length of the shorter feature. */
export const SYMMETRY: ToleranceTable<GeometricClass> = {
  ranges: [
    { from: 0, to: 100 },
    { from: 100, to: 300 },
    { from: 300, to: 1000 },
    { from: 1000, to: 3000 },
  ],
  values: {
    H: [0.5, 0.5, 0.5, 0.5],
    K: [0.6, 0.6, 0.8, 1],
    L: [0.6, 1, 1.5, 2],
  },
}

/** General tolerances on circular run-out, independent of size. */
export const CIRCULAR_RUN_OUT: ToleranceTable<GeometricClass> = {
  ranges: [{ from: 0, to: null }],
  values: {
    H: [0.1],
    K: [0.2],
    L: [0.5],
  },
}
