import { describe, expect, it } from 'vitest'

import {
  compileNumberPattern,
  hasPipeInCharacterClass,
  matchesNumberPattern,
  testNumberPattern,
} from '../numberPatternTest'

describe('matchesNumberPattern', () => {
  it('accepts anything when no pattern is configured', () => {
    expect(matchesNumberPattern('literally anything', '')).toBe(true)
  })

  it('matches in full, so an unanchored pattern rejects surrounding text', () => {
    // The whole point of mirroring Python's re.fullmatch: a forgotten ^...$
    // must not silently widen the rule.
    expect(matchesNumberPattern('P-001', 'P-\\d{3}')).toBe(true)
    expect(matchesNumberPattern('XXP-001YY', 'P-\\d{3}')).toBe(false)
  })

  it('treats explicit anchors as equivalent to none', () => {
    expect(matchesNumberPattern('P-001', '^P-\\d{3}$')).toBe(true)
    expect(matchesNumberPattern('P-0012', '^P-\\d{3}$')).toBe(false)
  })

  it('anchors a top-level alternation as a whole, not just its first branch', () => {
    expect(matchesNumberPattern('B-1', 'A-\\d|B-\\d')).toBe(true)
    expect(matchesNumberPattern('xB-1', 'A-\\d|B-\\d')).toBe(false)
  })

  it('fails open on a pattern that does not compile', () => {
    // The server is the authority; a client-only parse failure must never be
    // what blocks a user.
    expect(matchesNumberPattern('anything', '[')).toBe(true)
  })

  it('fails open on a pattern longer than the cap', () => {
    expect(matchesNumberPattern('anything', 'a'.repeat(201))).toBe(true)
  })
})

describe('compileNumberPattern', () => {
  it('returns null for the cases that fail open', () => {
    expect(compileNumberPattern('')).toBeNull()
    expect(compileNumberPattern('(')).toBeNull()
    expect(compileNumberPattern('a'.repeat(201))).toBeNull()
  })

  it('returns a usable regex otherwise', () => {
    expect(compileNumberPattern('P-\\d+')).toBeInstanceOf(RegExp)
  })
})

describe('testNumberPattern', () => {
  it('distinguishes "off" from "invalid" so the admin tab can say which', () => {
    expect(testNumberPattern('', 'P-001')).toBe('off')
    expect(testNumberPattern('[', 'P-001')).toBe('invalid')
  })

  it('reports match and mismatch against the sample', () => {
    expect(testNumberPattern('P-\\d{3}', 'P-001')).toBe('match')
    expect(testNumberPattern('P-\\d{3}', 'P-1')).toBe('mismatch')
  })
})

describe('hasPipeInCharacterClass', () => {
  it.each(['[M|V]\\d{5}', 'P[^|]', '[]|]'])('flags %s', (pattern) => {
    expect(hasPipeInCharacterClass(pattern)).toBe(true)
  })

  it.each(['(M|V)\\d{5}', '[MV]\\d{5}', 'P\\[|Q', '[\\]]|x', ''])('accepts %s', (pattern) => {
    expect(hasPipeInCharacterClass(pattern)).toBe(false)
  })
})
