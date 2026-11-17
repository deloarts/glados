import { describe, it, expect } from 'vitest'

import { importFieldsFor, isImportMappingComplete } from '../boughtItemsImportFields'

describe('importFieldsFor', () => {
  it('offers the EPLAN part number only with the lookup', () => {
    expect(importFieldsFor(false).map((f) => f.key)).not.toContain('edpPartNumber')
    expect(importFieldsFor(true).map((f) => f.key)).toContain('edpPartNumber')
  })

  it('needs name, order code and manufacturer only without the lookup', () => {
    expect(importFieldsFor(false).filter((f) => f.alwaysRequired).map((f) => f.key)).toEqual([
      'articleName',
      'orderCode1',
      'manufacturerName',
    ])
    expect(importFieldsFor(true).some((f) => f.alwaysRequired)).toBe(false)
    expect(isImportMappingComplete({ edpPartNumber: 'Artikelnummer' }, true)).toBe(true)
    expect(isImportMappingComplete({ edpPartNumber: 'Artikelnummer' }, false)).toBe(false)
  })
})
