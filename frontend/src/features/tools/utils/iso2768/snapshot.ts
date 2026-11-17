import { lookup } from './lookup'
import {
  ANGULAR,
  BROKEN_EDGES,
  CIRCULAR_RUN_OUT,
  LINEAR,
  PERPENDICULARITY,
  STRAIGHTNESS_FLATNESS,
  SYMMETRY,
} from './tables'
import type { GeometricClass, LinearClass, ToleranceTable } from './tables'

function rawValue<C extends string>(table: ToleranceTable<C>, cls: C, size: number): number | null {
  const result = lookup(table, cls, size)
  return result.ok ? result.value : null
}

/**
 * The general tolerances for one size as a saved-calculation snapshot: values
 * in mm, angles in minutes, as tabulated, independent of any number format.
 */
export function generalTolerancesSnapshot(
  designation: string,
  size: number | null,
  linear: LinearClass,
  geometric: GeometricClass | 'none',
): Record<string, unknown> {
  const n = size ?? Number.NaN
  return {
    designation,
    size,
    linear: rawValue(LINEAR, linear, n),
    brokenEdge: rawValue(BROKEN_EDGES, linear, n),
    angularMinutes: rawValue(ANGULAR, linear, n),
    geometric:
      geometric === 'none'
        ? null
        : {
            straightnessFlatness: rawValue(STRAIGHTNESS_FLATNESS, geometric, n),
            perpendicularity: rawValue(PERPENDICULARITY, geometric, n),
            symmetry: rawValue(SYMMETRY, geometric, n),
            circularRunOut: rawValue(CIRCULAR_RUN_OUT, geometric, n),
          },
  }
}
