import { AxiosError, type AxiosResponse } from 'axios'
import { describe, expect, it } from 'vitest'

import { productionErrorKey } from '../productionErrors'

function answered(code: string): AxiosError {
  const error = new AxiosError('Conflict')
  error.response = { status: 409, data: { detail: 'English detail', code } } as AxiosResponse
  return error
}

describe('productionErrorKey', () => {
  it('names the translation of a lot on hold', () => {
    expect(productionErrorKey(answered('LotOnHoldError'))).toBe('production.errors.lotOnHold')
  })

  it('leaves other codes and other errors to the detail', () => {
    expect(productionErrorKey(answered('SomeOtherError'))).toBeNull()
    expect(productionErrorKey(new Error('boom'))).toBeNull()
  })
})
