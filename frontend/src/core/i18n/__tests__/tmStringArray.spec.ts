import { describe, it, expect, afterEach } from 'vitest'

import { i18n } from '../index'
import { tmStringArray } from '../tmStringArray'

describe('tmStringArray', () => {
  afterEach(() => {
    i18n.global.locale.value = 'enGB'
  })

  it('returns the array for a key that resolves to a string array', () => {
    i18n.global.mergeLocaleMessage('enGB', { tmStringArrayTest: { arr: ['a', 'b', 'c'] } })

    expect(tmStringArray('tmStringArrayTest.arr')).toEqual(['a', 'b', 'c'])
  })

  it('returns an empty array for a key that resolves to a plain string', () => {
    i18n.global.mergeLocaleMessage('enGB', { tmStringArrayTest: { single: 'not an array' } })

    expect(tmStringArray('tmStringArrayTest.single')).toEqual([])
  })

  it('returns an empty array for a key that resolves to a mixed array', () => {
    i18n.global.mergeLocaleMessage('enGB', {
      tmStringArrayTest: { mixed: ['a', { nested: true }] },
    })

    expect(tmStringArray('tmStringArrayTest.mixed')).toEqual([])
  })

  it('returns an empty array for a key that does not exist', () => {
    expect(tmStringArray('tmStringArrayTest.doesNotExist')).toEqual([])
  })

  it('resolves against the currently active locale', () => {
    i18n.global.mergeLocaleMessage('enGB', { tmStringArrayTest: { locale: ['en-only'] } })
    i18n.global.mergeLocaleMessage('deAT', { tmStringArrayTest: { locale: ['de-only'] } })

    i18n.global.locale.value = 'deAT'

    expect(tmStringArray('tmStringArrayTest.locale')).toEqual(['de-only'])
  })
})
