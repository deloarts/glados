/**
 * Once in a while, the user drawer greets you by test-subject number instead of
 * your name.
 *
 * The roll happens when the drawer opens and the result lasts only for that
 * opening: close it and open it again and you are yourself, which is what
 * makes people doubt they saw it. A win is recorded against the calendar month
 * so it can happen at most once a month.
 */

import { safeStorage } from './safeStorage'

export const TEST_SUBJECT_KEY = 'testSubjectMonth'

/**
 * Per drawer-opening odds. High enough that most people get their one reveal
 * within a month, low enough that it is never the thing you expect to see.
 */
export const TEST_SUBJECT_CHANCE = 0.1

export function testSubjectName(userId: number): string {
  return `Test subject #${userId}`
}

/** Calendar month, `YYYY-MM`, in local time. */
export function monthKeyOf(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

function readMonth(): string | null {
  return safeStorage.get(TEST_SUBJECT_KEY)
}

// Blocked storage only costs the once-a-month cap.
function writeMonth(key: string): void {
  safeStorage.set(TEST_SUBJECT_KEY, key)
}

/**
 * Roll for a reveal, recording it when it wins.
 *
 * The month is written *only* on a win, so an unlucky month keeps rolling
 * rather than burning the allowance on the first drawer opening. `now` and
 * `random` are injectable so tests can pin the outcome.
 */
export function rollTestSubject(
  now: Date = new Date(),
  random: () => number = Math.random,
): boolean {
  const month = monthKeyOf(now)
  if (readMonth() === month) return false
  if (random() >= TEST_SUBJECT_CHANCE) return false

  writeMonth(month)
  return true
}
