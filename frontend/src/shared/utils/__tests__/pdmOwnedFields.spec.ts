import { describe, it, expect } from 'vitest'

import { isPdmLocked } from '../pdmOwnedFields'

describe('isPdmLocked', () => {
  it('is true when the field is in pdm_locked_fields', () => {
    expect(isPdmLocked({ pdm_locked_fields: ['article_name', 'gtin'] }, 'gtin')).toBe(true)
  })

  it('is true when the field is in pdm_locked_fields for a made item', () => {
    expect(isPdmLocked({ pdm_locked_fields: ['article_name', 'material'] }, 'article_name')).toBe(
      true,
    )
  })

  it('is false when the field is not in pdm_locked_fields', () => {
    expect(isPdmLocked({ pdm_locked_fields: ['article_name'] }, 'gtin')).toBe(false)
    expect(isPdmLocked({ pdm_locked_fields: ['article_name'] }, 'part_number')).toBe(false)
  })

  it('is false when pdm_locked_fields is empty', () => {
    expect(isPdmLocked({ pdm_locked_fields: [] }, 'article_name')).toBe(false)
  })

  it('is false when pdm_locked_fields is absent', () => {
    expect(isPdmLocked({}, 'article_name')).toBe(false)
  })

  it('is false when the item is null', () => {
    expect(isPdmLocked(null, 'article_name')).toBe(false)
  })
})
