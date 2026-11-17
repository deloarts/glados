import { compileNumberPattern } from '@/shared/utils/numberPattern'

export { compileNumberPattern, matchesNumberPattern, MAX_PATTERN_LENGTH } from '@/shared/utils/numberPattern'

export type PatternTestResult = 'off' | 'invalid' | 'match' | 'mismatch'

/** Drives the admin tab's live tester, which needs to tell "off" and "invalid" apart. */
export function testNumberPattern(pattern: string, sample: string): PatternTestResult {
  if (!pattern) return 'off'
  const re = compileNumberPattern(pattern)
  if (!re) return 'invalid'
  return re.test(sample) ? 'match' : 'mismatch'
}

/**
 * Whether a character class in the pattern contains "|". Inside brackets the
 * pipe is a literal character, not an alternative, so `[M|V]` also accepts
 * "|". It is a common slip, which is why the tab warns about it.
 */
export function hasPipeInCharacterClass(pattern: string): boolean {
  let inClass = false
  for (let i = 0; i < pattern.length; i++) {
    const c = pattern[i]
    if (c === '\\') {
      i++
      continue
    }
    if (inClass) {
      if (c === '|') return true
      if (c === ']') inClass = false
    } else if (c === '[') {
      inClass = true
      // A "]" right after "[" or "[^" is a literal member, not the end.
      if (pattern[i + 1] === '^') i++
      if (pattern[i + 1] === ']') i++
    }
  }
  return false
}
