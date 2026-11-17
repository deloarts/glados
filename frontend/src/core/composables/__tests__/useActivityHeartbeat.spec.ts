import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'

const getCurrentUser = vi.fn<() => Promise<unknown>>(async () => ({}))
vi.mock('@/core/api/users/getCurrentUser', () => ({ getCurrentUser: () => getCurrentUser() }))

import { idleHeaders, installUserActivityTracking } from '@/core/session/userActivity'
import { ACTIVITY_HEARTBEAT_MS, useActivityHeartbeat } from '../useActivityHeartbeat'

describe('useActivityHeartbeat', () => {
  let stop: () => void

  beforeEach(() => {
    vi.useFakeTimers()
    getCurrentUser.mockClear()
    stop = installUserActivityTracking()
    idleHeaders()
  })

  afterEach(() => {
    stop()
    vi.useRealTimers()
  })

  it('reports input that caused no request, and stays quiet while the user is idle', () => {
    const scope = effectScope()
    scope.run(() => useActivityHeartbeat())

    vi.advanceTimersByTime(ACTIVITY_HEARTBEAT_MS * 3)
    expect(getCurrentUser).not.toHaveBeenCalled()

    window.dispatchEvent(new KeyboardEvent('keydown'))
    vi.advanceTimersByTime(ACTIVITY_HEARTBEAT_MS)
    expect(getCurrentUser).toHaveBeenCalledOnce()

    scope.stop()
  })
})
