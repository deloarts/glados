import { describe, expect, it } from 'vitest'

import { formatElapsed } from '../formatDuration'

describe('formatElapsed', () => {
  it('shows seconds alone under a minute', () => {
    expect(formatElapsed('2026-10-09T10:00:00Z', '2026-10-09T10:00:45Z')).toBe('45s')
  })

  it('shows minutes and seconds from a minute on', () => {
    expect(formatElapsed('2026-10-09T10:00:00Z', '2026-10-09T10:03:12Z')).toBe('3m 12s')
  })

  it('never goes below zero', () => {
    expect(formatElapsed('2026-10-09T10:00:10Z', '2026-10-09T10:00:00Z')).toBe('0s')
  })
})
