import { describe, it, expect, beforeEach } from 'vitest'

import { setDisplayTimezone } from '@/core/utils/dates'
import { makeBroadcast } from '../../components/__tests__/terminalFixtures'
import {
  activeBroadcasts,
  audienceRequest,
  broadcastTagSeverity,
  quickPickUntil,
} from '../terminalBroadcasts'

describe('terminalBroadcasts', () => {
  beforeEach(() => {
    setDisplayTimezone('UTC')
  })

  it('sends every terminal, or only the lists the picked audience uses', () => {
    expect(audienceRequest('all', [1], [2])).toEqual({ all_terminals: true })
    expect(audienceRequest('terminals', [1], [2])).toEqual({
      all_terminals: false,
      terminal_ids: [1],
      infoscreen_ids: [],
    })
    expect(audienceRequest('infoscreens', [1], [2])).toEqual({
      all_terminals: false,
      terminal_ids: [],
      infoscreen_ids: [2],
    })
    expect(audienceRequest('both', [1], [2])).toEqual({
      all_terminals: false,
      terminal_ids: [1],
      infoscreen_ids: [2],
    })
  })

  it('picks 15 minutes, an hour and the end of the day on the wall clock', () => {
    const now = new Date('2026-11-03T10:07:42Z')
    const quarter = quickPickUntil('quarterHour', now)
    expect([quarter.getHours(), quarter.getMinutes(), quarter.getSeconds()]).toEqual([10, 22, 0])
    const hour = quickPickUntil('hour', now)
    expect([hour.getHours(), hour.getMinutes()]).toEqual([11, 7])
    const endOfDay = quickPickUntil('endOfDay', now)
    expect([endOfDay.getDate(), endOfDay.getHours(), endOfDay.getMinutes()]).toEqual([3, 23, 59])
  })

  it('keeps only the messages still shown', () => {
    const now = Date.parse('2026-11-03T10:00:00Z')
    const shown = makeBroadcast({ id: 1, show_until: '2026-11-03T11:00:00Z' })
    const past = makeBroadcast({ id: 2, show_until: '2026-11-03T09:00:00Z' })
    const ended = makeBroadcast({ id: 3, show_until: '2026-11-03T11:00:00Z', ended_at: '2026-11-03T09:30:00Z' })

    expect(activeBroadcasts([shown, past, ended], now)).toEqual([shown])
  })

  it('colours a warning as warn', () => {
    expect(broadcastTagSeverity('warning')).toBe('warn')
    expect(broadcastTagSeverity('danger')).toBe('danger')
    expect(broadcastTagSeverity('info')).toBe('info')
  })
})
