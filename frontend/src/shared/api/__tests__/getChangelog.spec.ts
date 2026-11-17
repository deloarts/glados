import { describe, it, expect, vi } from 'vitest'

const getMock = vi.fn<(url: string, config?: unknown) => Promise<{ data: string[] }>>()

vi.mock('@/core/api', () => ({
  default: { get: (...args: [string, unknown?]) => getMock(...args) },
}))

import { getChangelog } from '../getChangelog'

describe('getChangelog', () => {
  it('fetches the route and parses every line into an entry', async () => {
    getMock.mockResolvedValue({ data: ['2026-10-09 10:00, alice, Renamed, twice'] })

    const entries = await getChangelog('/projects/{project_id}/changelog', {
      path: { project_id: 4 },
    })

    expect(getMock).toHaveBeenCalledWith('/projects/4/changelog')
    expect(entries).toEqual([
      { timestamp: '2026-10-09 10:00', username: 'alice', message: 'Renamed, twice' },
    ])
  })
})
