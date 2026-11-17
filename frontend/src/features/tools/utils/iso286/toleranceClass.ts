import {
  deviationRangeIndex,
  itRangeIndex,
  mainRangeIndex,
  MAX_DEVIATION_SIZE,
  MAX_SIZE,
} from './sizeRanges'
import {
  DELTA,
  EXPLICIT_CLASSES,
  HOLE_RULES,
  IT_GRADES,
  MAX_GRADE,
  MIN_GRADE,
  SHAFT_RULES,
} from './tables'
import type { DeviationRule } from './tables'

export type FitPart = 'hole' | 'shaft'

/** Fundamental deviation letters in the order the standard lists them. */
export const SHAFT_LETTERS = [
  'a', 'c', 'd', 'e', 'f', 'g', 'h', 'js', 'j', 'k', 'm', 'n', 'p', 'r', 's', 'u', 'x',
] as const
export const HOLE_LETTERS = [
  'A', 'C', 'D', 'E', 'F', 'G', 'H', 'JS', 'J', 'K', 'M', 'N', 'P', 'R', 'S',
] as const

export const ALL_GRADES: readonly number[] = Array.from(
  { length: MAX_GRADE - MIN_GRADE + 1 },
  (_, i) => MIN_GRADE + i,
)

export interface ToleranceClass {
  part: FitPart
  letter: string
  grade: number
}

export type LimitFailure =
  | 'invalidSize'
  | 'sizeAboveRange'
  | 'unknownLetter'
  | 'gradeNotAvailable'
  | 'notForSmallSizes'

export type LimitResult =
  | { ok: true; upper: number; lower: number }
  | { ok: false; reason: LimitFailure }

export function classCode(cls: Pick<ToleranceClass, 'letter' | 'grade'>): string {
  return `${cls.letter}${cls.grade}`
}

/**
 * Parses a designation such as "H7" or "js6". Uppercase letters are holes,
 * lowercase letters shafts; a letter outside the supported set returns null.
 */
export function parseClass(code: string): ToleranceClass | null {
  const match = /^([A-Za-z]{1,2})(\d{1,2})$/.exec(code.trim())
  if (!match) return null
  const letter = match[1] as string
  const grade = Number(match[2])
  if (grade < MIN_GRADE || grade > MAX_GRADE) return null
  if ((HOLE_LETTERS as readonly string[]).includes(letter)) return { part: 'hole', letter, grade }
  if ((SHAFT_LETTERS as readonly string[]).includes(letter)) return { part: 'shaft', letter, grade }
  return null
}

function itValue(size: number, grade: number): number | null {
  const row = itRangeIndex(size)
  if (row === null) return null
  return IT_GRADES[row]?.[grade - MIN_GRADE] ?? null
}

function deltaValue(size: number, grade: number): number {
  const main = mainRangeIndex(size)
  if (main === null) return 0
  return DELTA[grade]?.[main] ?? 0
}

function fromRule(rule: DeviationRule, size: number, grade: number): LimitResult {
  if (grade < rule.grades[0] || grade > rule.grades[1]) {
    return { ok: false, reason: 'gradeNotAvailable' }
  }
  const it = itValue(size, grade)
  if (it === null) return { ok: false, reason: 'sizeAboveRange' }

  if (rule.kind === 'symmetric') return { ok: true, upper: it / 2, lower: -it / 2 }
  if (rule.kind === 'zero') {
    return rule.bound === 'upper'
      ? { ok: true, upper: 0, lower: -it }
      : { ok: true, upper: it, lower: 0 }
  }

  const row = deviationRangeIndex(size)
  if (row === null) return { ok: false, reason: 'sizeAboveRange' }
  const value = rule.values[row]
  if (value === undefined) return { ok: false, reason: 'sizeAboveRange' }

  if (rule.kind === 'lower') return { ok: true, upper: value + it, lower: value }
  if (rule.kind === 'shaftK') {
    const lower = grade >= 4 && grade <= 7 ? value : 0
    return { ok: true, upper: lower + it, lower }
  }
  const delta = rule.deltaUpTo !== undefined && grade <= rule.deltaUpTo ? deltaValue(size, grade) : 0
  const upper = value + delta
  return { ok: true, upper, lower: upper - it }
}

/**
 * Upper and lower limit deviation of a tolerance class at a nominal size, in
 * µm, or the reason the combination has no standard values.
 */
export function limitDeviations(size: number, cls: ToleranceClass): LimitResult {
  if (!Number.isFinite(size) || size <= 0) return { ok: false, reason: 'invalidSize' }
  if (size > MAX_SIZE) return { ok: false, reason: 'sizeAboveRange' }

  const explicit = EXPLICIT_CLASSES[classCode(cls)]
  if (explicit) {
    if (explicit.notUpTo !== undefined && size <= explicit.notUpTo) {
      return { ok: false, reason: 'notForSmallSizes' }
    }
    if (size > MAX_DEVIATION_SIZE) return { ok: false, reason: 'sizeAboveRange' }
    const pair = explicit.limits[deviationRangeIndex(size) ?? -1]
    if (!pair) return { ok: false, reason: 'sizeAboveRange' }
    return { ok: true, upper: pair[0], lower: pair[1] }
  }

  const rules = cls.part === 'hole' ? HOLE_RULES : SHAFT_RULES
  const rule = rules[cls.letter]
  const letters: readonly string[] = cls.part === 'hole' ? HOLE_LETTERS : SHAFT_LETTERS
  if (!letters.includes(cls.letter)) return { ok: false, reason: 'unknownLetter' }
  // Letters without a rule (u, x) only exist as explicit classes.
  if (!rule) return { ok: false, reason: 'gradeNotAvailable' }
  return fromRule(rule, size, cls.grade)
}

/** Grades that have standard values for this letter at this size. */
export function availableGrades(part: FitPart, letter: string, size: number): number[] {
  return ALL_GRADES.filter((grade) => limitDeviations(size, { part, letter, grade }).ok)
}

/**
 * The grade to keep when the letter changes: the current one when it is still
 * available, otherwise the closest available one (the lower on a tie), or
 * null when the letter has no grade at this size.
 */
export function closestGrade(available: readonly number[], current: number): number | null {
  if (available.includes(current)) return current
  let best: number | null = null
  for (const grade of available) {
    if (best === null || Math.abs(grade - current) < Math.abs(best - current)) best = grade
  }
  return best
}
