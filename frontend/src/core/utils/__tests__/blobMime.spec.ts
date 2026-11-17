import { describe, expect, it } from 'vitest'

import { withMimeFallback } from '../blobMime'

describe('withMimeFallback', () => {
  it('returns a typed blob unchanged', () => {
    const blob = new Blob(['x'], { type: 'image/png' })

    expect(withMimeFallback(blob, 'application/pdf')).toBe(blob)
  })

  it('types an untyped blob with the fallback and keeps its content size', () => {
    const blob = new Blob(['%PDF'])
    const typed = withMimeFallback(blob, 'application/pdf')

    expect(typed).not.toBe(blob)
    expect(typed.type).toBe('application/pdf')
    expect(typed.size).toBe(blob.size)
  })
})
