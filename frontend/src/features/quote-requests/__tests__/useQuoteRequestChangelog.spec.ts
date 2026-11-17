import { describe, it, expect, vi, beforeEach } from 'vitest'

const getMock = vi.fn<(url: string, config?: unknown) => Promise<{ data: string[] }>>()

vi.mock('@/core/api', () => ({
  default: { get: (...args: [string, unknown?]) => getMock(...args) },
}))

import { useQuoteRequestChangelog } from '../composables/useQuoteRequestChangelog'

describe('useQuoteRequestChangelog', () => {
  beforeEach(() => {
    getMock.mockReset()
  })

  it('reads the request changelog route and parses its lines', async () => {
    getMock.mockResolvedValue({ data: ['2026-10-31 09:15, buyer, Status changed to canceled'] })
    const changelog = useQuoteRequestChangelog(5)

    await changelog.reload()

    expect(getMock).toHaveBeenCalledWith('/quote-requests/5/changelog')
    expect(changelog.entries.value).toEqual([
      { timestamp: '2026-10-31 09:15', username: 'buyer', message: 'Status changed to canceled' },
    ])
    expect(changelog.loading.value).toBe(false)
    expect(changelog.error.value).toBe(false)
  })

  it('keeps the entries it showed and flags the error when a reload fails', async () => {
    getMock.mockResolvedValueOnce({ data: ['2026-10-31 09:15, buyer, Created'] })
    const changelog = useQuoteRequestChangelog(5)
    await changelog.reload()

    getMock.mockRejectedValueOnce(new Error('offline'))
    await changelog.reload()

    expect(changelog.entries.value).toHaveLength(1)
    expect(changelog.error.value).toBe(true)
    expect(changelog.loading.value).toBe(false)
  })
})
