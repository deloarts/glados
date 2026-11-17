import { describe, it, expect } from 'vitest'

import { isPublicId, publicIdFromCode } from '../publicId'

describe('isPublicId', () => {
  it('accepts a valid lowercase UUID', () => {
    expect(isPublicId('11111111-1111-1111-1111-111111111111')).toBe(true)
  })

  it('accepts a valid uppercase UUID', () => {
    expect(isPublicId('AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE')).toBe(true)
  })

  it('accepts a valid UUID padded with surrounding whitespace', () => {
    expect(isPublicId('  11111111-1111-1111-1111-111111111111  ')).toBe(true)
  })

  it('rejects an empty or whitespace-only string', () => {
    expect(isPublicId('')).toBe(false)
    expect(isPublicId('   ')).toBe(false)
  })

  it('rejects a non-UUID identifier', () => {
    expect(isPublicId('AX-2201')).toBe(false)
  })

  it('rejects a UUID with a missing segment', () => {
    expect(isPublicId('11111111-1111-1111-1111-11111111111')).toBe(false)
  })

  it('rejects a UUID with invalid characters', () => {
    expect(isPublicId('zzzzzzzz-1111-1111-1111-111111111111')).toBe(false)
  })
})

describe('publicIdFromCode', () => {
  const id = '7c1e0d2a-0000-4000-8000-000000000042'

  it('reads a bare public id', () => {
    expect(publicIdFromCode(`  ${id} `)).toBe(id)
  })

  it('reads the resolve link of a label or report page, whatever the host', () => {
    expect(publicIdFromCode(`https://glados.example.com/resolve/${id}`)).toBe(id)
    expect(publicIdFromCode(`http://10.0.0.5:5173/app/resolve/${id}/?from=label`)).toBe(id)
  })

  it('rejects other links and codes', () => {
    expect(publicIdFromCode('https://example.com/resolve/AX-2201')).toBeNull()
    expect(publicIdFromCode(`https://example.com/items/${id}`)).toBeNull()
    expect(publicIdFromCode('AX-2201')).toBeNull()
  })
})
