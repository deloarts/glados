import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type {
  AnnouncementBanner,
  MyAnnouncementsResponse,
  PendingAcknowledgement,
} from '../../types/announcementsTypes'

const getMyAnnouncementsMock = vi.fn<() => Promise<MyAnnouncementsResponse>>()
const acknowledgeAnnouncementMock = vi.fn<(publicId: string) => Promise<void>>()

vi.mock('../../api/getMyAnnouncements', () => ({
  getMyAnnouncements: () => getMyAnnouncementsMock(),
}))
vi.mock('../../api/acknowledgeAnnouncement', () => ({
  acknowledgeAnnouncement: (publicId: string) => acknowledgeAnnouncementMock(publicId),
}))

import { useAnnouncementsStore } from '../announcementsStore'

const STORAGE_KEY = 'glados.announcementBanner.dismissedUpdatedAt'

function makeBanner(overrides: Partial<AnnouncementBanner> = {}): AnnouncementBanner {
  return {
    text: 'We upgrade at 18:00.',
    severity: 'info',
    shows_from: null,
    shows_until: null,
    dismissable: true,
    updated_at: '2026-08-27T10:00:00Z',
    ...overrides,
  }
}

function makeAck(overrides: Partial<PendingAcknowledgement> = {}): PendingAcknowledgement {
  return {
    public_id: 'ack-1',
    text: 'Please read the new policy.',
    severity: 'warning',
    created_at: '2026-08-27T09:00:00Z',
    ...overrides,
  }
}

function response(
  banner: AnnouncementBanner | null,
  pending: PendingAcknowledgement[] = [],
): MyAnnouncementsResponse {
  return { banner, pending_acknowledgements: pending }
}

describe('announcementsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getMyAnnouncementsMock.mockReset()
    acknowledgeAnnouncementMock.mockReset()
    localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-27T12:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('refresh() populates banner and pendingAcknowledgements from GET /announcements/me', async () => {
    getMyAnnouncementsMock.mockResolvedValue(response(makeBanner(), [makeAck()]))
    const store = useAnnouncementsStore()

    await store.refresh()

    expect(store.banner).toEqual(makeBanner())
    expect(store.pendingAcknowledgements).toEqual([makeAck()])
  })

  it('visibleBanner is null when there is no banner', async () => {
    getMyAnnouncementsMock.mockResolvedValue(response(null))
    const store = useAnnouncementsStore()

    await store.refresh()

    expect(store.visibleBanner).toBeNull()
  })

  it('visibleBanner is null before shows_from', async () => {
    getMyAnnouncementsMock.mockResolvedValue(
      response(makeBanner({ shows_from: '2026-08-27T13:00:00Z' })),
    )
    const store = useAnnouncementsStore()
    await store.refresh()

    expect(store.visibleBanner).toBeNull()
  })

  it('visibleBanner is null after shows_until', async () => {
    getMyAnnouncementsMock.mockResolvedValue(
      response(makeBanner({ shows_until: '2026-08-27T11:00:00Z' })),
    )
    const store = useAnnouncementsStore()
    await store.refresh()

    expect(store.visibleBanner).toBeNull()
  })

  it('visibleBanner is visible inside its window', async () => {
    getMyAnnouncementsMock.mockResolvedValue(
      response(
        makeBanner({ shows_from: '2026-08-27T11:00:00Z', shows_until: '2026-08-27T13:00:00Z' }),
      ),
    )
    const store = useAnnouncementsStore()
    await store.refresh()

    expect(store.visibleBanner).not.toBeNull()
  })

  it('a window crossing is picked up by the 60s tick, with no server signal', async () => {
    getMyAnnouncementsMock.mockResolvedValue(
      response(makeBanner({ shows_until: '2026-08-27T12:00:30Z' })),
    )
    const store = useAnnouncementsStore()
    await store.refresh()
    store.startTicking()

    expect(store.visibleBanner).not.toBeNull()

    await vi.advanceTimersByTimeAsync(60_000)

    expect(store.visibleBanner).toBeNull()
    store.stopTicking()
  })

  it('dismissBanner() hides the banner and persists the dismissal to localStorage', async () => {
    getMyAnnouncementsMock.mockResolvedValue(response(makeBanner()))
    const store = useAnnouncementsStore()
    await store.refresh()

    store.dismissBanner()

    expect(store.visibleBanner).toBeNull()
    expect(localStorage.getItem(STORAGE_KEY)).toBe(makeBanner().updated_at)
  })

  it('a fresh store instance (simulating a reload) honours a dismissal already in localStorage', async () => {
    localStorage.setItem(STORAGE_KEY, makeBanner().updated_at)
    getMyAnnouncementsMock.mockResolvedValue(response(makeBanner()))
    const store = useAnnouncementsStore()
    await store.refresh()

    expect(store.visibleBanner).toBeNull()
  })

  it('editing the banner (a new updated_at) makes it reappear even though the old one was dismissed', async () => {
    getMyAnnouncementsMock.mockResolvedValue(response(makeBanner()))
    const store = useAnnouncementsStore()
    await store.refresh()
    store.dismissBanner()
    expect(store.visibleBanner).toBeNull()

    getMyAnnouncementsMock.mockResolvedValue(
      response(makeBanner({ text: 'Edited message.', updated_at: '2026-08-27T14:00:00Z' })),
    )
    await store.refresh()

    expect(store.visibleBanner?.text).toBe('Edited message.')
  })

  it('dismissBanner() still updates in-memory state when localStorage throws', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota exceeded')
    })
    getMyAnnouncementsMock.mockResolvedValue(response(makeBanner()))
    const store = useAnnouncementsStore()
    await store.refresh()

    expect(() => store.dismissBanner()).not.toThrow()
    expect(store.visibleBanner).toBeNull()
  })

  it('a store created while localStorage.getItem throws falls back to no dismissal, not a crash', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    expect(() => useAnnouncementsStore()).not.toThrow()
  })

  it('currentAcknowledgement is the first pending item; acknowledge() removes it and reveals the next', async () => {
    const first = makeAck({ public_id: 'ack-1' })
    const second = makeAck({ public_id: 'ack-2' })
    getMyAnnouncementsMock.mockResolvedValue(response(null, [first, second]))
    acknowledgeAnnouncementMock.mockResolvedValue(undefined)
    const store = useAnnouncementsStore()
    await store.refresh()

    expect(store.currentAcknowledgement?.public_id).toBe('ack-1')

    await store.acknowledge('ack-1')

    expect(acknowledgeAnnouncementMock).toHaveBeenCalledWith('ack-1')
    expect(store.currentAcknowledgement?.public_id).toBe('ack-2')

    await store.acknowledge('ack-2')

    expect(store.currentAcknowledgement).toBeNull()
  })

  it('startTicking() is idempotent and stopTicking() clears the interval (no further ticks)', async () => {
    getMyAnnouncementsMock.mockResolvedValue(
      response(makeBanner({ shows_until: '2026-08-27T12:00:30Z' })),
    )
    const store = useAnnouncementsStore()
    await store.refresh()

    store.startTicking()
    store.startTicking()
    store.stopTicking()

    await vi.advanceTimersByTimeAsync(120_000)

    // The window already lapsed at 12:00:30, but with the timer stopped
    // `now` never advanced past the initial refresh, so the banner is still
    // considered visible, proof the interval was actually cleared, not
    // just that nothing changed.
    expect(store.visibleBanner).not.toBeNull()
  })
})
