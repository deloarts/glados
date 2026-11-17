import { describe, it, expect } from 'vitest'

import {
  createDemandCommonCreateFields,
  demandCommonEditFieldsFromResponse,
  demandCommonFieldsToPayload,
  isDemandCommonCreateFieldsValid,
  parseDemandDate,
} from '../demandCommonFields'

describe('parseDemandDate', () => {
  it('returns null for a null input', () => {
    expect(parseDemandDate(null)).toBeNull()
  })

  it('parses an ISO date string', () => {
    const parsed = parseDemandDate('2026-01-15')
    expect(parsed).toBeInstanceOf(Date)
    expect(parsed?.getFullYear()).toBe(2026)
  })
})

describe('demandCommonEditFieldsFromResponse', () => {
  it('maps every response field, defaulting a null note to an empty string', () => {
    const fields = demandCommonEditFieldsFromResponse({
      quantity: 5,
      unit: 'PCS',
      items_per_unit: 2,
      high_priority: true,
      notify_on_delivery: false,
      desired_delivery_date: '2026-03-01',
      note: null,
    })

    expect(fields).toEqual({
      quantity: 5,
      unit: 'PCS',
      items_per_unit: 2,
      high_priority: true,
      notify_on_delivery: false,
      desired_delivery_date: parseDemandDate('2026-03-01'),
      note: '',
    })
  })

  it('keeps a present note as-is', () => {
    const fields = demandCommonEditFieldsFromResponse({
      quantity: 1,
      unit: 'PCS',
      items_per_unit: 1,
      high_priority: false,
      notify_on_delivery: false,
      desired_delivery_date: null,
      note: 'Handle with care',
    })

    expect(fields.note).toBe('Handle with care')
  })
})

describe('createDemandCommonCreateFields', () => {
  it('defaults to a null quantity and the given unit', () => {
    expect(createDemandCommonCreateFields('KG')).toEqual({
      quantity: null,
      unit: 'KG',
      items_per_unit: 1,
      high_priority: false,
      notify_on_delivery: false,
      desired_delivery_date: null,
      note: '',
    })
  })

  it('seeds the given quantity when provided', () => {
    expect(createDemandCommonCreateFields('KG', 12).quantity).toBe(12)
  })
})

describe('isDemandCommonCreateFieldsValid', () => {
  it('rejects a null quantity', () => {
    expect(isDemandCommonCreateFieldsValid(createDemandCommonCreateFields('PCS'))).toBe(false)
  })

  it('rejects a zero or negative quantity', () => {
    expect(isDemandCommonCreateFieldsValid(createDemandCommonCreateFields('PCS', 0))).toBe(false)
  })

  it('rejects a blank unit', () => {
    expect(isDemandCommonCreateFieldsValid(createDemandCommonCreateFields('   ', 5))).toBe(false)
  })

  it('accepts a positive quantity and a non-blank unit', () => {
    expect(isDemandCommonCreateFieldsValid(createDemandCommonCreateFields('PCS', 5))).toBe(true)
  })
})

describe('demandCommonFieldsToPayload', () => {
  it('trims the unit, formats the date and turns a blank note into null', () => {
    const payload = demandCommonFieldsToPayload({
      quantity: 5,
      unit: '  PCS  ',
      items_per_unit: 2,
      high_priority: true,
      notify_on_delivery: false,
      desired_delivery_date: new Date(2026, 0, 15),
      note: '   ',
    })

    expect(payload).toEqual({
      quantity: 5,
      unit: 'PCS',
      items_per_unit: 2,
      high_priority: true,
      notify_on_delivery: false,
      desired_delivery_date: '2026-01-15',
      note: null,
    })
  })

  it('keeps a non-blank note trimmed', () => {
    const payload = demandCommonFieldsToPayload({
      quantity: 1,
      unit: 'PCS',
      items_per_unit: 1,
      high_priority: false,
      notify_on_delivery: false,
      desired_delivery_date: null,
      note: '  Handle with care  ',
    })

    expect(payload.note).toBe('Handle with care')
    expect(payload.desired_delivery_date).toBeNull()
  })
})
