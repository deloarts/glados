// Mirrors src/modules/platform/domain/services/number_pattern.py on the backend so the admin
// can test a pattern as they type, and so the project/product forms can reject
// a bad number before the round trip. Keep in sync with that module.
//
// Python's re.fullmatch has no direct JS equivalent, so the pattern is wrapped
// in ^(?:...)$, the non-capturing group matters, otherwise a top-level
// alternation like "A|B" would anchor only its first branch.

export const MAX_PATTERN_LENGTH = 200

/** Compiles `pattern` as a full-match regex, or returns null if it is unusable. */
export function compileNumberPattern(pattern: string): RegExp | null {
  if (!pattern) return null
  if (pattern.length > MAX_PATTERN_LENGTH) return null
  try {
    return new RegExp(`^(?:${pattern})$`, 'u')
  } catch {
    return null
  }
}

/**
 * True if `value` satisfies `pattern`. An empty pattern accepts everything.
 *
 * A pattern that does not compile also accepts everything: the backend is the
 * authority, and failing open here means a user is never blocked by a rule the
 * client alone thinks was violated.
 */
export function matchesNumberPattern(value: string, pattern: string): boolean {
  if (!pattern) return true
  const re = compileNumberPattern(pattern)
  if (!re) return true
  return re.test(value)
}
