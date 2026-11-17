import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { safeStorage } from '@/core/utils/safeStorage'
import { getMyAnnouncements } from '../api/getMyAnnouncements'
import { acknowledgeAnnouncement as acknowledgeAnnouncementApi } from '../api/acknowledgeAnnouncement'
import type { AnnouncementBanner, PendingAcknowledgement } from '../types/announcementsTypes'

// Per browser, keyed on the banner's updated_at, so an edited banner
// reappears for someone who dismissed the old text. Not cleared on logout,
// since a dismissal is a fact about this browser.
const DISMISSED_BANNER_STORAGE_KEY = 'glados.announcementBanner.dismissedUpdatedAt'

// A local clock for re-evaluating the show window; data arrives only by
// push, never by this timer.
const TICK_INTERVAL_MS = 60_000

function readDismissedBannerUpdatedAt(): string | null {
  return safeStorage.get(DISMISSED_BANNER_STORAGE_KEY)
}

// Best effort: worst case the banner reappears next reload this tab.
function writeDismissedBannerUpdatedAt(updatedAt: string): void {
  safeStorage.set(DISMISSED_BANNER_STORAGE_KEY, updatedAt)
}

export const useAnnouncementsStore = defineStore('announcements', () => {
  const { loading, error, run } = useSequencedFetch(getMyAnnouncements)

  const banner = ref<AnnouncementBanner | null>(null)
  const pendingAcknowledgements = ref<PendingAcknowledgement[]>([])
  const dismissedBannerUpdatedAt = ref<string | null>(readDismissedBannerUpdatedAt())
  const now = ref(Date.now())

  let tickTimer: ReturnType<typeof setInterval> | null = null

  /**
   * The banner to show now: inside its window and not dismissed for this
   * updated_at. The API only returns enabled banners.
   */
  const visibleBanner = computed<AnnouncementBanner | null>(() => {
    const current = banner.value
    if (!current) return null
    if (current.shows_from && Date.parse(current.shows_from) > now.value) return null
    if (current.shows_until && Date.parse(current.shows_until) < now.value) return null
    if (dismissedBannerUpdatedAt.value === current.updated_at) return null
    return current
  })

  /** One at a time, oldest first; acknowledging reveals the next. */
  const currentAcknowledgement = computed<PendingAcknowledgement | null>(
    () => pendingAcknowledgements.value[0] ?? null,
  )

  async function refresh(): Promise<void> {
    const result = await run()
    if (!result) return
    banner.value = result.banner
    pendingAcknowledgements.value = result.pending_acknowledgements
  }

  function dismissBanner(): void {
    const current = banner.value
    if (!current) return
    dismissedBannerUpdatedAt.value = current.updated_at
    writeDismissedBannerUpdatedAt(current.updated_at)
  }

  async function acknowledge(publicId: string): Promise<void> {
    await acknowledgeAnnouncementApi(publicId)
    pendingAcknowledgements.value = pendingAcknowledgements.value.filter(
      (a) => a.public_id !== publicId,
    )
  }

  /**
   * Started and stopped with authentication, since resetting the store on
   * logout would not stop an interval.
   */
  function startTicking(): void {
    if (tickTimer !== null) return
    now.value = Date.now()
    tickTimer = setInterval(() => {
      now.value = Date.now()
    }, TICK_INTERVAL_MS)
  }

  function stopTicking(): void {
    if (tickTimer !== null) {
      clearInterval(tickTimer)
      tickTimer = null
    }
  }

  return {
    banner,
    pendingAcknowledgements,
    dismissedBannerUpdatedAt,
    now,
    loading,
    error,

    visibleBanner,
    currentAcknowledgement,

    refresh,
    dismissBanner,
    acknowledge,
    startTicking,
    stopTicking,
  }
})
