import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { formatMadeItemNumber, useMadeItemLabel } from '../madeItemLabel'
import { useHostStore } from '@/core/host/stores/hostStore'

describe('formatMadeItemNumber', () => {
  it('joins part number and revision with the given separator', () => {
    expect(formatMadeItemNumber('PN-1', 'A', ':')).toBe('PN-1:A')
  })

  it('respects an arbitrary separator', () => {
    expect(formatMadeItemNumber('PN-1', 'A', ' / ')).toBe('PN-1 / A')
  })

  it('falls back to the empty placeholder when the part number is null', () => {
    expect(formatMadeItemNumber(null, 'A', ':')).toBe('-:A')
  })

  it('falls back to the empty placeholder when the part number is undefined', () => {
    expect(formatMadeItemNumber(undefined, 'A', ':')).toBe('-:A')
  })

  it('returns the part number alone when the revision is null', () => {
    expect(formatMadeItemNumber('PN-1', null, ':')).toBe('PN-1')
  })

  it('returns the part number alone when the revision is undefined', () => {
    expect(formatMadeItemNumber('PN-1', undefined, ':')).toBe('PN-1')
  })

  it('returns the part number alone when the revision is an empty string', () => {
    expect(formatMadeItemNumber('PN-1', '', ':')).toBe('PN-1')
  })

  it('treats a numeric-looking "0" revision as present', () => {
    expect(formatMadeItemNumber('PN-1', '0', ':')).toBe('PN-1:0')
  })

  it('returns the empty placeholder alone when both are missing', () => {
    expect(formatMadeItemNumber(null, null, ':')).toBe('-')
  })
})

describe('useMadeItemLabel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('binds format() to the host store separator', () => {
    const hostStore = useHostStore()
    hostStore.madeItemPartNumbers.revision.separator = '-'

    const { format } = useMadeItemLabel()

    expect(format('PN-1', 'A')).toBe('PN-1-A')
  })

  it('reacts to a changed separator without re-creating the composable', () => {
    const hostStore = useHostStore()
    const { format } = useMadeItemLabel()

    expect(format('PN-1', 'A')).toBe('PN-1:A')

    hostStore.madeItemPartNumbers.revision.separator = '/'
    expect(format('PN-1', 'A')).toBe('PN-1/A')
  })
})
