import { describe, it, expect } from 'vitest'

import { severityColorVar } from '../severityColorVar'

describe('severityColorVar', () => {
  it.each([
    ['secondary', 'var(--p-surface-500)'],
    ['info', 'var(--p-blue-500)'],
    ['warn', 'var(--p-orange-500)'],
    ['help', 'var(--p-purple-500)'],
    ['success', 'var(--p-green-500)'],
    ['danger', 'var(--p-red-500)'],
    ['contrast', 'var(--p-surface-900)'],
  ])('maps severity %s to %s', (severity, expected) => {
    expect(severityColorVar(severity)).toBe(expected)
  })

  it('falls back to the surface color for an unknown severity', () => {
    expect(severityColorVar('not-a-real-severity')).toBe('var(--p-surface-500)')
  })
})
