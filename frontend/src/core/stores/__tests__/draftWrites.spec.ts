import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { DRAFT_WRITE_MS, cancelDraftWrite, flushDraftWrites, scheduleDraftWrite } from '../draftWrites'

describe('draftWrites', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    cancelDraftWrite('draft')
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('writes only the latest snapshot once the draft has been still', () => {
    const snapshot = vi.fn<() => unknown>().mockReturnValue({ rows: [2] })

    scheduleDraftWrite('draft', () => ({ rows: [1] }))
    vi.advanceTimersByTime(DRAFT_WRITE_MS - 1)
    scheduleDraftWrite('draft', snapshot)
    vi.advanceTimersByTime(DRAFT_WRITE_MS - 1)
    expect(localStorage.getItem('draft')).toBeNull()

    vi.advanceTimersByTime(1)
    expect(localStorage.getItem('draft')).toBe('{"rows":[2]}')
    expect(snapshot).toHaveBeenCalledTimes(1)
  })

  it('drops a cancelled write', () => {
    scheduleDraftWrite('draft', () => ({ rows: [1] }))
    cancelDraftWrite('draft')
    vi.advanceTimersByTime(DRAFT_WRITE_MS)

    expect(localStorage.getItem('draft')).toBeNull()
  })

  it('writes pending drafts at once when the page is hidden', () => {
    scheduleDraftWrite('draft', () => ({ rows: [1] }))
    window.dispatchEvent(new Event('pagehide'))

    expect(localStorage.getItem('draft')).toBe('{"rows":[1]}')
    flushDraftWrites()
  })

  it('does not throw when the storage quota is full', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('full', 'QuotaExceededError')
    })

    scheduleDraftWrite('draft', () => ({ rows: [1] }))

    expect(() => vi.advanceTimersByTime(DRAFT_WRITE_MS)).not.toThrow()
  })
})
