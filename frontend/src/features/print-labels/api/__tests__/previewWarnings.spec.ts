import { describe, it, expect } from 'vitest'

import { parsePreviewWarnings } from '../previewWarnings'

describe('parsePreviewWarnings', () => {
  it('splits the header on commas and drops blanks', () => {
    expect(parsePreviewWarnings('missing field, unknown font ,,')).toEqual([
      'missing field',
      'unknown font',
    ])
  })

  it('gives no warnings without a header', () => {
    expect(parsePreviewWarnings(undefined)).toEqual([])
    expect(parsePreviewWarnings('')).toEqual([])
  })
})
