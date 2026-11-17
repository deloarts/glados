import { computed, onScopeDispose, ref, watch } from 'vue'
import type { Ref } from 'vue'

import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { apiErrorStatus } from '@/core/utils/errors'
import {
  fetchMeetingFileBlob,
  getMeeting,
  getMeetingDistribution,
  getMeetingIssue,
  getMeetingOpenPoints,
  uploadMeetingFile,
} from '../api/meetingsApi'
import type {
  MeetingCardResponse,
  MeetingDistributionEntryResponse,
  MeetingIssueResponse,
  MeetingOpenPointResponse,
  MeetingResponse,
} from '../types/meetingResponse'

/**
 * The data of the meeting page: the meeting with its cards, the
 * distribution entries, the issue the next print and send carry with the
 * cards changed since the last send, the open points of a follow-up
 * meeting and the object URLs of its images. It follows other users' changes live, quietly,
 * and keeps the cards being edited untouched, since each card holds its own
 * editing state.
 */
export function useMeetingPage(meetingId: Ref<number>) {
  const meeting = ref<MeetingResponse | null>(null)
  const distribution = ref<MeetingDistributionEntryResponse[]>([])
  const openPoints = ref<MeetingOpenPointResponse[]>([])
  const issue = ref<MeetingIssueResponse | null>(null)
  const loading = ref(true)
  const notFound = ref(false)
  const loadError = ref(false)
  let epoch = 0

  async function loadSide(current: MeetingResponse): Promise<void> {
    const [entries, points, issued] = await Promise.all([
      getMeetingDistribution(current.id).catch(() => [] as MeetingDistributionEntryResponse[]),
      current.follow_up_of
        ? getMeetingOpenPoints(current.id).catch(() => [] as MeetingOpenPointResponse[])
        : Promise.resolve([] as MeetingOpenPointResponse[]),
      getMeetingIssue(current.id).catch(() => null),
    ])
    if (meeting.value?.id !== current.id) return
    distribution.value = entries
    openPoints.value = points
    issue.value = issued ?? null
  }

  /** Reads the meeting; a refetch after a live signal or an own change keeps the page as it is meanwhile. */
  async function load(quiet = false): Promise<void> {
    const current = ++epoch
    const id = meetingId.value
    if (!quiet) {
      loading.value = true
      notFound.value = false
      loadError.value = false
    }
    try {
      const loaded = await getMeeting(id)
      if (current !== epoch) return
      meeting.value = loaded
      await loadSide(loaded)
    } catch (err) {
      if (current !== epoch || quiet) return
      if (apiErrorStatus(err) === 404) notFound.value = true
      else loadError.value = true
    } finally {
      if (current === epoch) loading.value = false
    }
  }

  watch(
    meetingId,
    (id) => {
      if (!Number.isInteger(id)) return
      meeting.value = null
      issue.value = null
      void load()
    },
    { immediate: true },
  )

  // A follow-up shows the open todos of the meetings before it, so their
  // changes count as well.
  const watchedIds = computed(() => new Set([meetingId.value, ...openPoints.value.map((point) => point.meeting.id)]))
  useLiveRefresh([LiveResource.MEETINGS], () => load(true), {
    filter: (signal) => watchedIds.value.has(signal.id),
  })

  function replaceCard(card: MeetingCardResponse): void {
    const current = meeting.value
    if (!current) return
    const exists = current.cards.some((entry) => entry.id === card.id)
    meeting.value = {
      ...current,
      cards: exists ? current.cards.map((entry) => (entry.id === card.id ? card : entry)) : [...current.cards, card],
    }
  }

  function removeCard(cardId: number): void {
    const current = meeting.value
    if (current) meeting.value = { ...current, cards: current.cards.filter((card) => card.id !== cardId) }
  }

  // ── Images ──────────────────────────────────────────────────────────

  const imageUrls = new Map<number, string>()
  const imageVersion = ref(0)
  const loadingImages = new Set<number>()

  async function loadImage(meetingIdValue: number, fileId: number): Promise<void> {
    if (imageUrls.has(fileId) || loadingImages.has(fileId)) return
    loadingImages.add(fileId)
    try {
      const blob = await fetchMeetingFileBlob(meetingIdValue, fileId)
      imageUrls.set(fileId, URL.createObjectURL(blob))
      imageVersion.value += 1
    } catch {
      // The image shows as its alt text.
    } finally {
      loadingImages.delete(fileId)
    }
  }

  watch(
    () => meeting.value?.files,
    (files) => {
      const current = meeting.value
      if (!current || !files) return
      for (const file of files) if (file.category === 'image') void loadImage(current.id, file.id)
    },
    { immediate: true },
  )

  function revokeImages(): void {
    imageUrls.forEach((url) => URL.revokeObjectURL(url))
    imageUrls.clear()
  }

  watch(meetingId, revokeImages)
  onScopeDispose(revokeImages)

  function imageUrl(fileId: number): string | undefined {
    return imageUrls.get(fileId)
  }

  /** Uploads an image pasted into a card and returns it for the card's text. */
  async function uploadCardImage(file: File, cardId: number): Promise<{ id: number; name: string } | null> {
    const current = meeting.value
    if (!current) return null
    const uploaded = await uploadMeetingFile(current.id, file, cardId)
    const fresh = meeting.value
    if (fresh?.id === current.id) meeting.value = { ...fresh, files: [...fresh.files, uploaded] }
    return { id: uploaded.id, name: uploaded.file_name }
  }

  return {
    meeting,
    distribution,
    openPoints,
    issue,
    loading,
    notFound,
    loadError,
    load,
    replaceCard,
    removeCard,
    imageUrl,
    imageVersion,
    uploadCardImage,
  }
}
