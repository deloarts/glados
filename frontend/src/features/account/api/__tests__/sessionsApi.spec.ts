import { describe, it, expect, vi, beforeEach } from 'vitest'

const getMock = vi.fn<(url: string) => Promise<{ data: unknown }>>()
const deleteMock = vi.fn<(url: string) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    delete: (url: string) => deleteMock(url),
  },
}))

import {
  fetchSessions,
  revokeSession,
  revokeOtherSessions,
  fetchTrustedDevices,
  revokeTrustedDevice,
  revokeAllTrustedDevices,
} from '../sessionsApi'
import type { SessionSummary, TrustedDeviceSummary } from '../sessionsApi'

function makeSession(overrides: Partial<SessionSummary> = {}): SessionSummary {
  return {
    id: 1,
    public_id: 'session-1',
    created_at: '2026-01-01T00:00:00Z',
    last_seen_at: '2026-01-02T00:00:00Z',
    user_agent: 'Firefox',
    ip: '127.0.0.1',
    is_current: true,
    ...overrides,
  }
}

function makeDevice(overrides: Partial<TrustedDeviceSummary> = {}): TrustedDeviceSummary {
  return {
    id: 1,
    public_id: 'device-1',
    created_at: '2026-01-01T00:00:00Z',
    last_used_at: '2026-01-02T00:00:00Z',
    expires_at: '2026-06-01T00:00:00Z',
    user_agent: 'Firefox',
    ...overrides,
  }
}

describe('sessionsApi', () => {
  beforeEach(() => {
    getMock.mockReset()
    deleteMock.mockReset()
  })

  it('fetchSessions GETs /users/me/sessions/ and returns the list', async () => {
    const sessions = [makeSession()]
    getMock.mockResolvedValue({ data: sessions })

    const result = await fetchSessions()

    expect(getMock).toHaveBeenCalledWith('/users/me/sessions/')
    expect(result).toBe(sessions)
  })

  it('revokeSession DELETEs /users/me/sessions/{publicId}', async () => {
    deleteMock.mockResolvedValue({ data: undefined })

    await revokeSession('session-1')

    expect(deleteMock).toHaveBeenCalledWith('/users/me/sessions/session-1')
  })

  it('revokeOtherSessions DELETEs the sessions collection and returns the revoked count', async () => {
    deleteMock.mockResolvedValue({ data: { revoked: 3 } })

    const result = await revokeOtherSessions()

    expect(deleteMock).toHaveBeenCalledWith('/users/me/sessions/')
    expect(result).toBe(3)
  })

  it('fetchTrustedDevices GETs /users/me/trusted-devices/ and returns the list', async () => {
    const devices = [makeDevice()]
    getMock.mockResolvedValue({ data: devices })

    const result = await fetchTrustedDevices()

    expect(getMock).toHaveBeenCalledWith('/users/me/trusted-devices/')
    expect(result).toBe(devices)
  })

  it('revokeTrustedDevice DELETEs /users/me/trusted-devices/{publicId}', async () => {
    deleteMock.mockResolvedValue({ data: undefined })

    await revokeTrustedDevice('device-1')

    expect(deleteMock).toHaveBeenCalledWith('/users/me/trusted-devices/device-1')
  })

  it('revokeAllTrustedDevices DELETEs the trusted-devices collection and returns the revoked count', async () => {
    deleteMock.mockResolvedValue({ data: { revoked: 5 } })

    const result = await revokeAllTrustedDevices()

    expect(deleteMock).toHaveBeenCalledWith('/users/me/trusted-devices/')
    expect(result).toBe(5)
  })

  it('propagates a failed fetchSessions request instead of swallowing it', async () => {
    const error = new Error('401 unauthorized')
    getMock.mockRejectedValue(error)

    await expect(fetchSessions()).rejects.toBe(error)
  })
})
