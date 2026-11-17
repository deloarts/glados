import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { getNotifications } from '../api/getNotifications'
import { markAllNotificationsRead } from '../api/markAllNotificationsRead'
import { markNotificationRead } from '../api/markNotificationRead'
import type { NotificationResponse } from '../types/notificationTypes'

const POLL_INTERVAL_MS = 60_000

export const useNotificationsStore = defineStore('notifications', () => {
  const { loading, error, run } = useSequencedFetch(getNotifications)
  const notifications = ref<NotificationResponse[]>([])
  let pollTimer: ReturnType<typeof setInterval> | null = null

  const unreadNotifications = computed(() => notifications.value.filter((n) => !n.is_read))

  const unreadCount = computed(() => unreadNotifications.value.length)

  async function refresh(): Promise<void> {
    const result = await run()
    if (result) notifications.value = result
  }

  function startPolling(): void {
    if (pollTimer !== null) return
    // A poll tick that fails (session expired, transient network error) must
    // not become an unhandled rejection; the next tick retries regardless.
    refresh().catch(() => {})
    pollTimer = setInterval(() => {
      refresh().catch(() => {})
    }, POLL_INTERVAL_MS)
  }

  function stopPolling(): void {
    if (pollTimer !== null) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  async function markRead(notificationId: number): Promise<void> {
    await markNotificationRead(notificationId)
    const n = notifications.value.find((n) => n.id === notificationId)
    if (n) n.is_read = true
  }

  async function markAllRead(): Promise<void> {
    await markAllNotificationsRead()
    notifications.value.forEach((n) => (n.is_read = true))
  }

  return {
    notifications,
    loading,
    error,
    unreadNotifications,
    unreadCount,
    refresh,
    startPolling,
    stopPolling,
    markRead,
    markAllRead,
  }
})
