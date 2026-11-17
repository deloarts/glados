import type { FitType } from './iso286/fit'

export type FitSystem = 'hole' | 'shaft' | 'both'

/**
 * A preferred fit from DIN 7157. Series 1 is preferred over series 2.
 * `descriptionKey` points at a title and a typical use under
 * `tools.fitCalculator.recommendations.descriptions`; the fits the standard
 * lists without an application example have none.
 */
export interface FitRecommendation {
  hole: string
  shaft: string
  series: 1 | 2
  system: FitSystem
  group: FitType
  descriptionKey?: string
  /** Recommended only for nominal sizes up to and including this size. */
  maxSize?: number
  /** Recommended only for nominal sizes above this size. */
  minSize?: number
}

export const FIT_RECOMMENDATIONS: readonly FitRecommendation[] = [
  { hole: 'C11', shaft: 'h9', series: 1, system: 'shaft', group: 'clearance' },
  { hole: 'C11', shaft: 'h11', series: 2, system: 'shaft', group: 'clearance' },
  { hole: 'D10', shaft: 'h11', series: 2, system: 'shaft', group: 'clearance' },
  { hole: 'H11', shaft: 'h9', series: 2, system: 'both', group: 'clearance' },
  { hole: 'H8', shaft: 'd9', series: 2, system: 'hole', group: 'clearance', descriptionKey: 'largeClearance' },
  { hole: 'D10', shaft: 'h9', series: 1, system: 'shaft', group: 'clearance', descriptionKey: 'largeClearance' },
  { hole: 'H8', shaft: 'e8', series: 2, system: 'hole', group: 'clearance', descriptionKey: 'noticeableClearance' },
  { hole: 'E9', shaft: 'h9', series: 1, system: 'shaft', group: 'clearance', descriptionKey: 'noticeableClearance' },
  { hole: 'H8', shaft: 'f7', series: 1, system: 'hole', group: 'clearance', descriptionKey: 'largerClearance' },
  { hole: 'F8', shaft: 'h9', series: 1, system: 'shaft', group: 'clearance', descriptionKey: 'largerClearance' },
  { hole: 'H7', shaft: 'f7', series: 1, system: 'hole', group: 'clearance', descriptionKey: 'smallClearance' },
  { hole: 'F8', shaft: 'h6', series: 1, system: 'shaft', group: 'clearance', descriptionKey: 'smallClearance' },
  { hole: 'H7', shaft: 'g6', series: 2, system: 'hole', group: 'clearance', descriptionKey: 'slightClearance' },
  { hole: 'G7', shaft: 'h6', series: 2, system: 'shaft', group: 'clearance', descriptionKey: 'slightClearance' },
  { hole: 'H8', shaft: 'h9', series: 1, system: 'both', group: 'clearance', descriptionKey: 'barelyNoticeableClearance' },
  { hole: 'H7', shaft: 'h6', series: 1, system: 'both', group: 'clearance', descriptionKey: 'verySlightClearance' },
  { hole: 'H7', shaft: 'j6', series: 2, system: 'hole', group: 'transition', descriptionKey: 'mostlyClearance' },
  { hole: 'H7', shaft: 'k6', series: 2, system: 'hole', group: 'transition' },
  { hole: 'H7', shaft: 'n6', series: 1, system: 'hole', group: 'transition', descriptionKey: 'mostlyInterference' },
  { hole: 'H7', shaft: 'r6', series: 1, system: 'hole', group: 'interference', descriptionKey: 'slightInterference' },
  { hole: 'H7', shaft: 's6', series: 2, system: 'hole', group: 'interference', descriptionKey: 'ampleInterference' },
  { hole: 'H8', shaft: 'u8', series: 1, system: 'hole', group: 'interference', descriptionKey: 'largeInterference', minSize: 24 },
  { hole: 'H8', shaft: 'x8', series: 1, system: 'hole', group: 'interference', descriptionKey: 'veryLargeInterference', maxSize: 24 },
]

export function findRecommendation(hole: string, shaft: string): FitRecommendation | undefined {
  return FIT_RECOMMENDATIONS.find((r) => r.hole === hole && r.shaft === shaft)
}

/** Whether the size lies in the range the recommendation is meant for. */
export function isRecommendedForSize(rec: FitRecommendation, size: number): boolean {
  if (rec.maxSize !== undefined && size > rec.maxSize) return false
  if (rec.minSize !== undefined && size <= rec.minSize) return false
  return true
}
