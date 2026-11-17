export type FitType = 'clearance' | 'transition' | 'interference'

export interface Fit {
  /** Largest clearance, hole upper minus shaft lower deviation, in µm. */
  maxClearance: number
  /** Smallest clearance in µm; negative when the parts interfere. */
  minClearance: number
  type: FitType
}

export type FitFigureKind = 'maxClearance' | 'minClearance' | 'maxInterference' | 'minInterference'

export interface FitFigure {
  kind: FitFigureKind
  /** Always positive or zero, in µm. */
  value: number
}

/**
 * The two figures that describe a fit of its type: largest and smallest
 * clearance for a clearance fit, largest clearance and largest interference
 * for a transition fit, largest and smallest interference for an
 * interference fit.
 */
export function fitFigures(fit: Fit): FitFigure[] {
  if (fit.type === 'clearance') {
    return [
      { kind: 'maxClearance', value: fit.maxClearance },
      { kind: 'minClearance', value: fit.minClearance },
    ]
  }
  if (fit.type === 'interference') {
    return [
      { kind: 'maxInterference', value: -fit.minClearance },
      { kind: 'minInterference', value: -fit.maxClearance },
    ]
  }
  return [
    { kind: 'maxClearance', value: fit.maxClearance },
    { kind: 'maxInterference', value: -fit.minClearance },
  ]
}

/**
 * Pairs a hole and a shaft by their limit deviations (µm). A fit is a
 * clearance fit when even the smallest hole is not smaller than the largest
 * shaft, an interference fit when even the largest hole is not larger than the
 * smallest shaft, and a transition fit otherwise.
 */
export function calculateFit(
  hole: { upper: number; lower: number },
  shaft: { upper: number; lower: number },
): Fit {
  const maxClearance = hole.upper - shaft.lower
  const minClearance = hole.lower - shaft.upper
  let type: FitType = 'transition'
  if (minClearance >= 0) type = 'clearance'
  else if (maxClearance <= 0) type = 'interference'
  return { maxClearance, minClearance, type }
}
