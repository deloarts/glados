import { computed, ref } from 'vue'
import type { Ref } from 'vue'

import type { MeetingDistributionEntryResponse, MeetingIssueResponse, MeetingResponse } from '../types/meetingResponse'
import { useMeetingNotesPdf } from './useMeetingNotesPdf'

/**
 * Print, send and the snapshots of the meeting page: which dialog is open,
 * the snapshot it shows and on which tab, the cards changed or added since
 * the last send for their tags, and the PDF builder the print and send
 * dialogs share.
 */
export function useMeetingDistribution(
  meeting: Ref<MeetingResponse | null>,
  issue: Ref<MeetingIssueResponse | null>,
  distribution: Ref<MeetingDistributionEntryResponse[]>,
) {
  const { build } = useMeetingNotesPdf(meeting)

  const printVisible = ref(false)
  const sendVisible = ref(false)
  const snapshotVisible = ref(false)
  const snapshotId = ref<number | null>(null)
  const snapshotTab = ref<'as' | 'changes'>('as')

  const changedCardIds = computed(() => new Set(issue.value?.last_sent_at ? issue.value.changed_card_ids : []))
  const addedCardIds = computed(() => new Set(issue.value?.last_sent_at ? issue.value.added_card_ids : []))

  /** The snapshot of the newest send, which Show Changes compares with. */
  const lastSentSnapshotId = computed(
    () => distribution.value.find((entry) => entry.kind === 'sent' && entry.snapshot_id !== null)?.snapshot_id ?? null,
  )

  function openSnapshot(id: number, tab: 'as' | 'changes' = 'as'): void {
    snapshotId.value = id
    snapshotTab.value = tab
    snapshotVisible.value = true
  }

  function showChangesSinceSend(): void {
    const id = lastSentSnapshotId.value
    if (id !== null) openSnapshot(id, 'changes')
  }

  return {
    build,
    printVisible,
    sendVisible,
    snapshotVisible,
    snapshotId,
    snapshotTab,
    changedCardIds,
    addedCardIds,
    lastSentSnapshotId,
    openSnapshot,
    showChangesSinceSend,
  }
}
