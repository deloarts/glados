import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const getNotificationsMock = vi.fn<() => Promise<unknown[]>>()

vi.mock('../../api/getNotifications', () => ({
  getNotifications: () => getNotificationsMock(),
}))
vi.mock('../../api/markAllNotificationsRead', () => ({
  markAllNotificationsRead: vi.fn<() => Promise<void>>(),
}))
vi.mock('../../api/markNotificationRead', () => ({
  markNotificationRead: vi.fn<() => Promise<void>>(),
}))

import { useNotificationsStore } from '../notificationsStore'

// startPolling handles errors on every tick: a poll tick failing (session
// expired, network blip) must not become an unhandled promise rejection, it
// is just retried on the next tick.
describe('notificationsStore.startPolling', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('does not throw an unhandled rejection when a poll tick fails', async () => {
    getNotificationsMock.mockRejectedValue(new Error('401'))
    const store = useNotificationsStore()

    const unhandled = vi.fn<() => void>()
    process.once('unhandledRejection', unhandled)

    store.startPolling()
    await vi.advanceTimersByTimeAsync(0)

    expect(unhandled).not.toHaveBeenCalled()
    store.stopPolling()
  })

  it('keeps retrying on the next tick after a failed poll', async () => {
    getNotificationsMock.mockRejectedValueOnce(new Error('network error'))
    getNotificationsMock.mockResolvedValueOnce([])
    const store = useNotificationsStore()

    store.startPolling()
    await vi.advanceTimersByTimeAsync(0)
    expect(getNotificationsMock).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(60_000)
    expect(getNotificationsMock).toHaveBeenCalledTimes(2)

    store.stopPolling()
  })

  it('populates notifications on a successful poll', async () => {
    getNotificationsMock.mockResolvedValue([{ id: 1, is_read: false }])
    const store = useNotificationsStore()

    store.startPolling()
    await vi.advanceTimersByTimeAsync(0)

    expect(store.unreadCount).toBe(1)
    store.stopPolling()
  })
})
