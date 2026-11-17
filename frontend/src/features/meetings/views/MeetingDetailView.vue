<script setup lang="ts">
import { computed, nextTick, ref, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePageTitle } from '@/core/composables/usePageTitle'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useUsersStore } from '@/core/stores/usersStore'
import { formatISODateTime } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { usePhoneLayout } from '@/core/composables/usePhoneLayout'
import EmptyState from '@/shared/components/EmptyState.vue'
import PanelResizeHandle from '@/shared/components/layout/PanelResizeHandle.vue'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useResizablePanelWidth } from '@/shared/composables/useResizablePanelWidth'
import { createFollowUpMeeting, createMeetingCard } from '../api/meetingsApi'
import { useCardPresence } from '../composables/useCardPresence'
import { useMeetingDistribution } from '../composables/useMeetingDistribution'
import { useMeetingNotesDrafts } from '../composables/useMeetingNotesDrafts'
import { useMeetingPage } from '../composables/useMeetingPage'
import { meetingNotesTabPath, meetingPath } from '../utils/meetingRoutes'
import { todoOwnerOptions } from '../utils/todoOwners'
import MeetingCard from '../components/MeetingCard.vue'
import MeetingControls from '../components/MeetingControls.vue'
import MeetingDistributionCard from '../components/MeetingDistributionCard.vue'
import MeetingDocumentsCard from '../components/MeetingDocumentsCard.vue'
import MeetingFormDialog from '../components/MeetingFormDialog.vue'
import MeetingHistoryDialog from '../components/MeetingHistoryDialog.vue'
import MeetingInfoBar from '../components/MeetingInfoBar.vue'
import MeetingInfoCard from '../components/MeetingInfoCard.vue'
import MeetingNotesDraftsNotice from '../components/MeetingNotesDraftsNotice.vue'
import MeetingOpenPointsCard from '../components/MeetingOpenPointsCard.vue'
import MeetingPrintDialog from '../components/MeetingPrintDialog.vue'
import MeetingSendDialog from '../components/MeetingSendDialog.vue'
import MeetingSentChangesNotice from '../components/MeetingSentChangesNotice.vue'
import MeetingSnapshotDialog from '../components/MeetingSnapshotDialog.vue'
import MeetingValidityDialog from '../components/MeetingValidityDialog.vue'
import type { MeetingCardResponse, MeetingEventResponse, MeetingResponse } from '../types/meetingResponse'

/**
 * The page of one meeting below its project or product, without the tab
 * strip: the notes as cards on the left, and the Meeting, Documents and
 * Distribution cards on the right, with Open Points on a follow-up meeting.
 * Print and Send build the PDF in the browser; a card changed since the
 * last send is tagged, and the Distribution card and the history open the
 * snapshot of every print, download and send.
 * Every card saves on its own, so several people write at once; the page
 * follows their changes live and shows who edits which card. An invalid
 * meeting is read-only until a manager restores it.
 */
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useAppToast()
const usersStore = useUsersStore()
const currentUserStore = useCurrentUserStore()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()
const { phoneMode } = usePhoneLayout()
// The side column (meeting, documents, distribution) resizes as one by its
// leading edge, as on the order page.
const {
  width: sideWidth,
  isResizing: isResizingSide,
  onResizeStart: onSideResizeStart,
  onResizeKey: onSideResizeKey,
  min: sideMin,
  max: sideMax,
} = useResizablePanelWidth({
  defaultWidth: 400,
  min: 280,
  max: () => window.innerWidth * 0.6,
  dockedTo: 'end',
  storageKey: 'glados.meetings.detailSideWidth',
})

const meetingId = computed(() => Number(route.params.meetingId))
const page = useMeetingPage(meetingId)
const { meeting, loading, notFound, loadError, distribution, openPoints, issue, imageVersion } = page
watchLoadingBar(loading)
void usersStore.ensureLoaded()

const presence = useCardPresence(() => currentUserStore.user?.id)
const { drafts } = useMeetingNotesDrafts(() => (meeting.value ? { meeting_id: meeting.value.id } : null))

const canWrite = computed(() => hasPermission(Permission.WRITE_MEETINGS))
const writeBlocked = computed(() => missing(Permission.WRITE_MEETINGS))
const canSend = computed(() => canWrite.value && hasPermission(Permission.SEND_MAIL))
const sendBlocked = computed(() => missing(Permission.WRITE_MEETINGS, Permission.SEND_MAIL))

const {
  build: buildNotes,
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
} = useMeetingDistribution(meeting, issue, distribution)

function openHistorySnapshot(event: MeetingEventResponse): void {
  const id = event.details?.snapshot_id
  if (typeof id === 'number') openSnapshot(id)
}
const ownerOptions = computed(() => (meeting.value ? todoOwnerOptions(meeting.value, usersStore.users) : []))
const openTodoCount = computed(
  () => meeting.value?.cards.reduce((sum, card) => sum + card.todos.filter((todo) => !todo.done).length, 0) ?? 0,
)

const editVisible = ref(false)
const validityVisible = ref(false)
const validityMode = ref<'invalidate' | 'restore'>('invalidate')
const historyVisible = ref(false)
const busy = ref(false)

const documents = useTemplateRef<{ pick: () => void }>('documents')
const cardRefs = new Map<number, { startEditing: () => Promise<void> }>()

function setCardRef(cardId: number, element: unknown): void {
  if (element) cardRefs.set(cardId, element as { startEditing: () => Promise<void> })
  else cardRefs.delete(cardId)
}

function editorNames(cardId: number): string[] {
  return presence
    .editorsOf(cardId)
    .map((userId) => usersStore.users.find((user) => user.id === userId)?.full_name ?? t('meetings.unknownUser'))
}

// The tab to go back to, from the meeting once it is known and from the
// route before that.
const backPath = computed(() => {
  if (meeting.value) return meetingNotesTabPath(meeting.value.owner)
  const kind = route.name === 'ProductMeeting' ? 'product' : 'project'
  return meetingNotesTabPath({ kind, id: Number(route.params.id) })
})

let scrolled = false
watch(meeting, async (current) => {
  if (!current) return
  // A link that names another owner than the meeting's own moves on to the right page.
  const expected = meetingPath(current)
  if (!route.path.startsWith(expected)) {
    await router.replace({ path: expected, hash: route.hash })
    return
  }
  if (!scrolled && route.hash.startsWith('#card-')) {
    scrolled = true
    await nextTick()
    document.getElementById(route.hash.slice(1))?.scrollIntoView({ block: 'start' })
  }
})

async function uploadImage(file: File, cardId: number): Promise<{ id: number; name: string } | null> {
  try {
    return await page.uploadCardImage(file, cardId)
  } catch (err) {
    toast.error(file.name, extractApiError(err) ?? t('meetings.errors.unknown'))
    return null
  }
}

async function addCard(): Promise<void> {
  const current = meeting.value
  if (!current) return
  busy.value = true
  try {
    const card = await createMeetingCard(current.id, { body: '', internal: false })
    page.replaceCard(card)
    await nextTick()
    document.getElementById(`card-${card.id}`)?.scrollIntoView({ block: 'center' })
    await cardRefs.get(card.id)?.startEditing()
  } catch (err) {
    toast.error(current.meeting_number, extractApiError(err) ?? t('meetings.errors.unknown'))
  } finally {
    busy.value = false
  }
}

async function createFollowUp(): Promise<void> {
  const current = meeting.value
  if (!current) return
  busy.value = true
  try {
    const followUp = await createFollowUpMeeting(current.id)
    toast.success(followUp.meeting_number, t('meetings.toasts.followUpCreated'))
    await router.push(meetingPath(followUp))
  } catch (err) {
    toast.error(current.meeting_number, extractApiError(err) ?? t('meetings.errors.unknown'))
  } finally {
    busy.value = false
  }
}

function openValidity(mode: 'invalidate' | 'restore'): void {
  validityMode.value = mode
  validityVisible.value = true
}

function onMeetingSaved(saved: MeetingResponse): void {
  meeting.value = saved
  void page.load(true)
}

function onCardUpdated(card: MeetingCardResponse): void {
  page.replaceCard(card)
  void page.load(true)
}

function onCardDeleted(cardId: number): void {
  page.removeCard(cardId)
  void page.load(true)
}

const invalidNotice = computed(() => {
  const current = meeting.value
  if (!current || current.valid) return ''
  return t('meetings.invalidNotice', {
    name: current.invalid_by?.full_name ?? t('meetings.unknownUser'),
    at: current.invalid_at ? formatISODateTime(current.invalid_at) : '',
    reason: current.invalid_reason ?? '',
  })
})

const { setPageTitle } = usePageTitle()
watch(
  () => meeting.value?.meeting_number ?? t('meetings.title'),
  (title) => setPageTitle(title),
  { immediate: true },
)
</script>

<template>
  <PageLayout
    :card="false"
    wrap-menu
    data-class="meeting-view-data"
    :class="{ 'is-resizing-ew': isResizingSide }"
  >
    <template #info>
      <MeetingInfoBar :meeting="meeting" />
    </template>
    <template #controls>
      <MeetingControls
        :meeting="meeting"
        :busy="busy"
        :can-distribute="!!issue"
        @back="router.push(backPath)"
        @edit="editVisible = true"
        @add-card="addCard"
        @add-file="documents?.pick()"
        @print="printVisible = true"
        @send="sendVisible = true"
        @history="historyVisible = true"
        @invalidate="openValidity('invalidate')"
        @restore="openValidity('restore')"
        @follow-up="createFollowUp"
      />
    </template>

    <div v-if="loading && !meeting" class="state-center" />
    <div v-else-if="notFound" class="state-center state-message" data-testid="meeting-not-found">
      <i class="mdi mdi-alert-circle-outline state-icon" aria-hidden="true" />
      <span>{{ t('meetings.errors.notFound') }}</span>
    </div>
    <div v-else-if="loadError" class="state-center state-message" data-testid="meeting-load-error">
      <i class="mdi mdi-alert-outline state-icon" aria-hidden="true" />
      <span>{{ t('meetings.errors.load') }}</span>
    </div>

    <div v-else-if="meeting" class="meeting-page" :class="{ phone: phoneMode }">
      <div class="meeting-main">
        <Message v-if="!meeting.valid" severity="error" data-testid="meeting-invalid-notice">
          {{ invalidNotice }}
        </Message>
        <MeetingSentChangesNotice
          :issue="issue"
          :valid="meeting.valid"
          :can-send="canSend"
          :send-blocked="sendBlocked"
          :has-snapshot="lastSentSnapshotId !== null"
          @show-changes="showChangesSinceSend"
          @send-again="sendVisible = true"
        />
        <MeetingNotesDraftsNotice :drafts="drafts" />

        <SectionCard
          :title="t('meetings.notes.title')"
          icon="mdi-note-text-outline"
          :hint="meeting.valid ? t('meetings.notes.hint') : t('meetings.readOnly')"
          class="notes-card"
        >
          <template #title-end>
            <Tag
              :value="t('meetings.notes.count', { cards: meeting.cards.length, todos: openTodoCount })"
              severity="secondary"
              data-testid="meeting-card-count"
            />
          </template>
          <div v-if="meeting.cards.length" class="cards">
            <MeetingCard
              v-for="card in meeting.cards"
              :key="card.id"
              :ref="(element) => setCardRef(card.id, element)"
              :meeting="meeting"
              :card="card"
              :can-write="canWrite"
              :write-blocked="writeBlocked"
              :editors="editorNames(card.id)"
              :owner-options="ownerOptions"
              :image-url="page.imageUrl"
              :image-version="imageVersion"
              :upload-image="uploadImage"
              @updated="onCardUpdated"
              @changed="page.load(true)"
              @deleted="onCardDeleted"
            >
              <template #tags>
                <Tag
                  v-if="changedCardIds.has(card.id)"
                  :value="t('meetings.changedAfterSending')"
                  icon="mdi mdi-email-alert-outline"
                  severity="warn"
                  :data-testid="`meeting-card-changed-${card.id}`"
                />
                <Tag
                  v-else-if="addedCardIds.has(card.id)"
                  :value="t('meetings.addedAfterSending')"
                  icon="mdi mdi-email-plus-outline"
                  severity="warn"
                  :data-testid="`meeting-card-added-${card.id}`"
                />
              </template>
            </MeetingCard>
          </div>
          <EmptyState v-else icon="mdi mdi-note-plus-outline" :message="t('meetings.notes.empty')" />
          <div v-if="meeting.valid" class="add-card">
            <span v-tooltip.top="writeBlocked || undefined">
              <Button
                :label="t('meetings.addCard')"
                icon="mdi mdi-plus"
                severity="secondary"
                outlined
                :disabled="!canWrite || busy"
                data-testid="meeting-add-card-bottom"
                @click="addCard"
              />
            </span>
          </div>
        </SectionCard>
      </div>

      <PanelResizeHandle
        v-if="!phoneMode"
        :width="sideWidth"
        :min="sideMin"
        :max="sideMax"
        @start="onSideResizeStart"
        @key="onSideResizeKey"
      />
      <aside class="side-cards" :style="phoneMode ? undefined : { width: `${sideWidth}px` }">
        <MeetingOpenPointsCard
          v-if="meeting.follow_up_of"
          :points="openPoints"
          :can-write="canWrite"
          :write-blocked="writeBlocked"
          class="open-points-card"
          @changed="page.load(true)"
        />
        <MeetingInfoCard :meeting="meeting" class="info-card" @updated="onMeetingSaved" />
        <MeetingDocumentsCard
          ref="documents"
          class="documents-card"
          :meeting="meeting"
          :can-write="canWrite"
          :write-blocked="writeBlocked"
          @changed="page.load(true)"
        />
        <MeetingDistributionCard :entries="distribution" class="distribution-card">
          <template #actions="{ entry }">
            <template v-if="entry.snapshot_id !== null">
              <Button
                :label="t(`meetings.distribution.view.${entry.kind}`)"
                icon="mdi mdi-eye-outline"
                size="small"
                text
                :data-testid="`meeting-distribution-view-${entry.journal_entry_id}`"
                @click="openSnapshot(entry.snapshot_id, 'as')"
              />
              <Button
                :label="t('meetings.distribution.changesSince')"
                icon="mdi mdi-file-compare"
                size="small"
                text
                :data-testid="`meeting-distribution-changes-${entry.journal_entry_id}`"
                @click="openSnapshot(entry.snapshot_id, 'changes')"
              />
            </template>
          </template>
        </MeetingDistributionCard>
      </aside>
    </div>

    <template v-if="meeting">
      <MeetingFormDialog v-model:visible="editVisible" :meeting="meeting" @saved="onMeetingSaved" />
      <MeetingValidityDialog
        v-model:visible="validityVisible"
        :meeting="meeting"
        :mode="validityMode"
        @saved="onMeetingSaved"
      />
      <MeetingHistoryDialog
        v-model:visible="historyVisible"
        :meeting-id="meeting.id"
        :meeting-number="meeting.meeting_number"
        can-open-snapshots
        @open-snapshot="openHistorySnapshot"
      />
      <MeetingPrintDialog
        v-model:visible="printVisible"
        :meeting="meeting"
        :issue="issue"
        :build="buildNotes"
        @done="page.load(true)"
        @outdated="page.load(true)"
      />
      <MeetingSendDialog
        v-model:visible="sendVisible"
        :meeting="meeting"
        :issue="issue"
        :build="buildNotes"
        @sent="page.load(true)"
        @outdated="page.load(true)"
      />
      <MeetingSnapshotDialog
        v-model:visible="snapshotVisible"
        :meeting="meeting"
        :snapshot-id="snapshotId"
        :tab="snapshotTab"
        :image-url="page.imageUrl"
        :image-version="imageVersion"
      />
    </template>
  </PageLayout>
</template>

<style scoped lang="scss">
// The notes and the side column scroll each on their own, never the page.
:deep(.meeting-view-data) {
  overflow: hidden;
}

.is-resizing-ew {
  user-select: none;
  cursor: ew-resize;
}

.meeting-page {
  height: 100%;
  min-height: 0;
  display: flex;
  // The drag handle provides the visible spacing.
  gap: var(--space-1);

  // A phone stacks the side cards under the notes and scrolls the page.
  &.phone {
    flex-direction: column;
    gap: var(--space-2);
    height: auto;
  }
}

.meeting-main {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  overflow-y: auto;

  > * {
    flex-shrink: 0;
  }

  // The notes reach down to the bottom and grow with their cards.
  > .notes-card {
    flex: 1 0 auto;
  }

  .phone & {
    overflow: visible;
  }
}

.cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.add-card {
  display: flex;
  justify-content: center;
  margin-top: var(--space-2);
}

.side-cards {
  flex: 0 0 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  overflow-y: auto;

  > .open-points-card,
  > .info-card,
  > .distribution-card {
    flex: 0 0 auto;
  }

  // The documents take the height left, so the distribution sits at the
  // bottom; a long list scrolls inside the card.
  > .documents-card {
    flex: 1 1 0;
    min-height: 10rem;
  }

  > .distribution-card {
    max-height: 40%;
  }

  .phone & {
    overflow: visible;

    > .documents-card {
      flex: 0 0 auto;
    }

    > .distribution-card {
      max-height: none;
    }
  }
}

.state-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: var(--space-3);
}

.state-message {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-md);

  .state-icon {
    font-size: var(--font-size-3xl);
  }
}
</style>
