import { describe, it, expect } from 'vitest'

import {
  OFFLINE_AFTER_MS,
  isOffline,
  isPairingCodeFormat,
  normalisePairingCode,
  screenSize,
} from '../terminalStatus'
import { makeTerminal } from '../../components/__tests__/terminalFixtures'

describe('terminalStatus', () => {
  const now = Date.parse('2026-10-30T10:00:00Z')

  it('counts an approved terminal unseen for more than five minutes as offline', () => {
    const seenAt = (ms: number) => new Date(now - ms).toISOString()

    expect(isOffline(makeTerminal({ last_seen_at: seenAt(OFFLINE_AFTER_MS - 1000) }), now)).toBe(false)
    expect(isOffline(makeTerminal({ last_seen_at: seenAt(OFFLINE_AFTER_MS + 1000) }), now)).toBe(true)
  })

  it('never calls a pending or revoked terminal offline', () => {
    const seenAtLongAgo = '2026-10-01T00:00:00Z'
    expect(isOffline(makeTerminal({ status: 'pending', last_seen_at: seenAtLongAgo }), now)).toBe(false)
    expect(isOffline(makeTerminal({ status: 'revoked', last_seen_at: seenAtLongAgo }), now)).toBe(false)
  })

  it('normalises a typed code and checks its format', () => {
    expect(normalisePairingCode(' abc-def ')).toBe('ABCDEF')
    expect(isPairingCodeFormat('ABCDEF')).toBe(true)
    expect(isPairingCodeFormat('K7M2QX')).toBe(true)
    expect(isPairingCodeFormat('ABCDE')).toBe(false)
    expect(isPairingCodeFormat('ABCDEFG')).toBe(false)
    expect(isPairingCodeFormat('ABCDE0')).toBe(false)
    expect(isPairingCodeFormat('ABCDEO')).toBe(false)
    expect(isPairingCodeFormat('ABCDE1')).toBe(false)
    expect(isPairingCodeFormat('ABCDEI')).toBe(false)
    expect(isPairingCodeFormat('ABCDEL')).toBe(false)
  })

  it('shows the screen size only when both sides are known', () => {
    expect(screenSize(makeTerminal({ screen_width: 1920, screen_height: 1080 }))).toBe('1920 × 1080')
    expect(screenSize(makeTerminal({ screen_width: null, screen_height: 1080 }))).toBeNull()
  })
})
