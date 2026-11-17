import { describe, it, expect, vi, beforeEach } from 'vitest'

const getMock = vi.fn<(url: string) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: { get: (url: string) => getMock(url) },
}))

import { getAutoPlanRunStatus } from '../getAutoPlanRunStatus'
import type { AutoPlanRunStatus } from '../../types/scheduleBoardResponse'

describe('getAutoPlanRunStatus', () => {
  beforeEach(() => {
    getMock.mockReset()
  })

  it('GETs /production-schedule/auto-plan/status and returns a running snapshot as-is', async () => {
    const status: AutoPlanRunStatus = {
      running: true,
      run: {
        run_id: 'a1b2c3',
        user_id: 3,
        user_name: 'Jane Doe',
        started_at: '2026-08-24T10:00:00Z',
        stage: 'placing',
        current: 2,
        total: 10,
      },
    }
    getMock.mockResolvedValue({ data: status })

    const result = await getAutoPlanRunStatus()

    expect(getMock).toHaveBeenCalledWith('/production-schedule/auto-plan/status')
    expect(result).toBe(status)
  })

  it('returns running: false with a null run when idle', async () => {
    const status: AutoPlanRunStatus = { running: false, run: null }
    getMock.mockResolvedValue({ data: status })

    const result = await getAutoPlanRunStatus()

    expect(result).toEqual(status)
  })

  it('propagates a failed request instead of swallowing it', async () => {
    const error = new Error('network down')
    getMock.mockRejectedValue(error)

    await expect(getAutoPlanRunStatus()).rejects.toBe(error)
  })
})
