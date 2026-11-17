import { describe, expect, it } from 'vitest'

import { formatAddress } from '../address'

describe('formatAddress', () => {
  it('joins street, postal code and city', () => {
    expect(formatAddress({ street: 'Main Street 1', postal_code: '1010', city: 'Vienna' })).toBe(
      'Main Street 1, 1010 Vienna',
    )
  })

  it('leaves out missing and blank parts with their separators', () => {
    expect(formatAddress({ street: 'Main Street 1', postal_code: null, city: ' ' })).toBe('Main Street 1')
    expect(formatAddress({ street: '', postal_code: '1010', city: 'Vienna' })).toBe('1010 Vienna')
    expect(formatAddress({ street: null, postal_code: '', city: undefined })).toBe('')
  })
})
