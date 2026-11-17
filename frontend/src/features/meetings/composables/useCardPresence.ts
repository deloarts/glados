import { onScopeDispose, ref, watch } from 'vue'
import type { Ref } from 'vue'

import { useLiveStore } from '@/core/realtime/liveStore'
import { LiveResource } from '@/core/realtime/resources'
import type { LiveSignal } from '@/core/realtime/types'
import { announceMeetingCardPresence } from '../api/meetingsApi'

export const PRESENCE_HEARTBEAT_MS = 20_000
export const PRESENCE_EXPIRY_MS = 45_000
const PRESENCE_TICK_MS = 5_000

/**
 * Who else edits which card of the meeting page, from the live
 * `meeting-card-presence` signal: an editor's heartbeat names the card and
 * the editor, and the editor counts as editing until 45 seconds after the
 * last one, or until the signal says they stopped. The viewer's own
 * heartbeats are left out.
 */
export function useCardPresence(ownUserId: () => number | null | undefined) {
  const live = useLiveStore()
  const seen = ref(new Map<number, Map<number, number>>())
  const now = ref(Date.now())

  function onSignal(signal: LiveSignal): void {
    const userId = signal.actor_id
    if (userId === null || userId === ownUserId()) return
    const next = new Map(seen.value)
    const editors = new Map(next.get(signal.id) ?? [])
    if (signal.action === 'deleted') editors.delete(userId)
    else editors.set(userId, Date.now())
    next.set(signal.id, editors)
    seen.value = next
    now.value = Date.now()
  }

  const off = live.on(LiveResource.MEETING_CARD_PRESENCE, onSignal)
  const timer = setInterval(() => {
    now.value = Date.now()
  }, PRESENCE_TICK_MS)

  onScopeDispose(() => {
    off()
    clearInterval(timer)
  })

  /** The users editing the card now, without the viewer. */
  function editorsOf(cardId: number): number[] {
    const editors = seen.value.get(cardId)
    if (!editors) return []
    return [...editors].filter(([, at]) => now.value - at < PRESENCE_EXPIRY_MS).map(([userId]) => userId)
  }

  return { editorsOf }
}

/**
 * The heartbeat of a card the user edits: one at once, then every 20
 * seconds while `editing` holds, and an end signal when it stops or the card
 * goes away. A failed heartbeat is dropped, since the next one follows.
 */
export function useCardHeartbeat(meetingId: () => number, cardId: () => number, editing: Ref<boolean>): void {
  let timer: ReturnType<typeof setInterval> | null = null

  function beat(state: boolean): void {
    announceMeetingCardPresence(meetingId(), cardId(), state).catch(() => {})
  }

  function stop(announce: boolean): void {
    if (timer) {
      clearInterval(timer)
      timer = null
      if (announce) beat(false)
    }
  }

  watch(
    editing,
    (active) => {
      if (active && !timer) {
        beat(true)
        timer = setInterval(() => beat(true), PRESENCE_HEARTBEAT_MS)
      } else if (!active) {
        stop(true)
      }
    },
    { immediate: true },
  )

  onScopeDispose(() => stop(true))
}
