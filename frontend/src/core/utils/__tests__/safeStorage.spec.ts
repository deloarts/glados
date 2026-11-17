import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'

import { safeStorage } from '../safeStorage'

describe('safeStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('reads, writes and removes values', () => {
    expect(safeStorage.get('a')).toBeNull()
    expect(safeStorage.set('a', '1')).toBe(true)
    expect(safeStorage.get('a')).toBe('1')
    expect(safeStorage.keys()).toEqual(['a'])
    expect(safeStorage.remove('a')).toBe(true)
    expect(safeStorage.get('a')).toBeNull()
  })

  it('reports a failed write instead of throwing, as on a full quota', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('full', 'QuotaExceededError')
    })

    expect(safeStorage.set('a', '1')).toBe(false)
  })

  it('treats blocked storage as empty', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })

    expect(safeStorage.get('a')).toBeNull()
    expect(safeStorage.remove('a')).toBe(false)
  })

  it('treats a runtime without localStorage as empty', () => {
    vi.stubGlobal('localStorage', undefined)

    expect(safeStorage.get('a')).toBeNull()
    expect(safeStorage.set('a', '1')).toBe(false)
    expect(safeStorage.remove('a')).toBe(false)
    expect(safeStorage.keys()).toEqual([])
  })
})
