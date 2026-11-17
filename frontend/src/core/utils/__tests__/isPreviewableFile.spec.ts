import { describe, expect, it } from 'vitest'

import { isPreviewableFile } from '../meshFile'

describe('isPreviewableFile', () => {
  it('accepts a PDF, an image and a mesh', () => {
    expect(isPreviewableFile('drawing.pdf', 'application/pdf')).toBe(true)
    expect(isPreviewableFile('photo.jpg', 'image/jpeg')).toBe(true)
    expect(isPreviewableFile('part.stl', 'application/octet-stream')).toBe(true)
  })

  it('rejects anything else, also without a mime type', () => {
    expect(isPreviewableFile('part.step', 'application/step')).toBe(false)
    expect(isPreviewableFile('notes.txt', null)).toBe(false)
    expect(isPreviewableFile('notes.txt', undefined)).toBe(false)
  })
})
