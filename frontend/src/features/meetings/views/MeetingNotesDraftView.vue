<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useConfirm } from 'openvue/useconfirm'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePageTitle } from '@/core/composables/usePageTitle'
import { useUsersStore } from '@/core/stores/usersStore'
import { formatISODateTime } from '@/core/utils/dates'
import { apiErrorStatus, extractApiError } from '@/core/utils/errors'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { HelpButton } from '@/shared/help'
import {
  applyMeetingNotesDraft,
  discardMeetingNotesDraft,
  getMeetingNotesDraft,
} from '../api/meetingNotesDraftsApi'
import { formatMeetingWhen, formatNextMeeting } from '../utils/meetingDates'
import { applyRequest, initialReview } from '../utils/meetingNotesDraft'
import type { MeetingNotesReviewState, PersonChoice } from '../utils/meetingNotesDraft'
import { meetingNotesTabPath, meetingPath } from '../utils/meetingRoutes'
import MeetingNotesDraftCardForm from '../components/MeetingNotesDraftCardForm.vue'
import MeetingNotesDraftPeople from '../components/MeetingNotesDraftPeople.vue'
import type { MeetingNotesDraftResponse } from '../types/meetingNotesDraft'

/**
 * The review of a draft of meeting notes an AI agent prepared from a record
 * of the meeting, such as handwritten notes. Only its creator sees it. The
 * person matches each name once to a user, a contact, a guest or nobody,
 * keeps, edits or leaves out each card, and applies the draft, which adds
 * the cards with their decisions and todos to the meeting, or creates the
 * meeting first, and only then notifies the todo owners. Discarding deletes
 * the draft and changes nothing else.
 */
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useAppToast()
const confirm = useConfirm()
const usersStore = useUsersStore()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()

const draftId = computed(() => Number(route.params.id))
const draft = ref<MeetingNotesDraftResponse | null>(null)
const review = ref<MeetingNotesReviewState | null>(null)
const loading = ref(false)
const notFound = ref(false)
const loadError = ref(false)
const busy = ref(false)
const submitted = ref(false)
watchLoadingBar(loading)
void usersStore.ensureLoaded()

const canWrite = computed(() => hasPermission(Permission.WRITE_MEETINGS))
const writeBlocked = computed(() => missing(Permission.WRITE_MEETINGS))

async function load(): Promise<void> {
  loading.value = true
  notFound.value = false
  loadError.value = false
  try {
    const loaded = await getMeetingNotesDraft(draftId.value)
    draft.value = loaded
    review.value = initialReview(loaded)
  } catch (err) {
    if (apiErrorStatus(err) === 404) notFound.value = true
    else loadError.value = true
  } finally {
    loading.value = false
  }
}
watch(draftId, () => void load(), { immediate: true })

const attendeeNames = computed(() => new Set(review.value?.attendees.map((a) => a.name) ?? []))
const keptCards = computed(() => review.value?.cards.filter((card) => card.include).length ?? 0)
const nameError = computed(() =>
  submitted.value && review.value?.newMeeting && !review.value.newMeeting.name.trim()
    ? t('meetings.drafts.nameRequired')
    : '',
)

const title = computed(() => draft.value?.name ?? t('meetings.drafts.title'))
const { setPageTitle } = usePageTitle()
watch(title, (value) => setPageTitle(value), { immediate: true })

const targetLabel = computed(() => {
  const current = draft.value
  if (!current) return ''
  if (current.meeting_id !== null) {
    return t('meetings.drafts.addsTo', { number: current.meeting_number ?? '' })
  }
  return current.project_id !== null
    ? t('meetings.drafts.newOfProject', { number: current.owner_number ?? '' })
    : t('meetings.drafts.newOfProduct', { number: current.owner_number ?? '' })
})

const backPath = computed(() => {
  const current = draft.value
  if (!current) return '/'
  if (current.meeting_id !== null) return `/meetings/${current.meeting_id}`
  return current.project_id !== null
    ? meetingNotesTabPath({ kind: 'project', id: current.project_id })
    : meetingNotesTabPath({ kind: 'product', id: current.product_id ?? 0 })
})

function personLabel(written: string): string {
  const choice: PersonChoice | undefined = review.value?.people[written]
  const match = draft.value?.people.find((p) => p.written === written)
  const suggested = match?.candidates.find((c) => `${c.kind}:${c.id}` === choice)
  if (suggested) return suggested.name
  if (choice?.startsWith('user:')) {
    const id = Number(choice.slice(5))
    return usersStore.users.find((user) => user.id === id)?.full_name ?? written
  }
  return written
}

const nextMeeting = computed(() =>
  review.value ? formatNextMeeting(review.value.next_meeting_date, review.value.next_meeting_time) : null,
)

async function apply(): Promise<void> {
  const current = review.value
  if (!current || !draft.value) return
  submitted.value = true
  if (nameError.value || keptCards.value === 0) return
  busy.value = true
  try {
    const result = await applyMeetingNotesDraft(draft.value.id, applyRequest(current))
    toast.success(result.meeting.meeting_number, t('meetings.drafts.applied', { count: keptCards.value }))
    await router.push(meetingPath(result.meeting))
  } catch (err) {
    toast.error(title.value, extractApiError(err) ?? t('meetings.errors.unknown'))
  } finally {
    busy.value = false
  }
}

function askDiscard(): void {
  confirm.require({
    header: t('meetings.drafts.discardHeader'),
    message: t('meetings.drafts.discardConfirm'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary', text: true },
    acceptProps: { label: t('meetings.drafts.discard'), severity: 'danger', icon: 'mdi mdi-delete-outline' },
    accept: () => void discard(),
  })
}

async function discard(): Promise<void> {
  if (!draft.value) return
  const back = backPath.value
  busy.value = true
  try {
    await discardMeetingNotesDraft(draft.value.id)
    toast.success(title.value, t('meetings.drafts.discarded'))
    await router.push(back)
  } catch (err) {
    toast.error(title.value, extractApiError(err) ?? t('meetings.errors.unknown'))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <PageLayout :card="false" wrap-menu data-class="draft-view-data">
    <template #info>
      <InfoBar>
        <template v-if="draft">
          <span class="info-title" data-testid="draft-info-title">{{ t('meetings.drafts.title') }}</span>
          <span class="info-sep" />
          <Tag
            v-tooltip.bottom="draft.token_name ? t('agents.badge.tooltip', { token: draft.token_name }) : undefined"
            :value="t('agents.badge.label')"
            icon="mdi mdi-robot-outline"
            severity="info"
          />
          <Tag :value="t('meetings.drafts.status')" severity="warn" />
          <span class="info-sep" />
          <span class="info-name">{{ targetLabel }}</span>
          <span class="info-sep" />
          <span class="info-muted">
            <i class="mdi mdi-clock-outline" aria-hidden="true" />
            {{ t('meetings.drafts.created', { at: formatISODateTime(draft.created) }) }}
          </span>
        </template>
      </InfoBar>
    </template>
    <template #controls>
      <ControlsBar data-testid="draft-controls">
        <template #start>
          <Button
            icon="mdi mdi-arrow-left"
            :label="t('meetings.back')"
            severity="contrast"
            text
            data-testid="draft-back"
            @click="router.push(backPath)"
          />
          <template v-if="draft">
            <span v-tooltip.bottom="writeBlocked || undefined">
              <Button
                icon="mdi mdi-check"
                :label="t('meetings.drafts.apply')"
                severity="contrast"
                text
                :disabled="!canWrite || busy || keptCards === 0"
                data-testid="draft-apply"
                @click="apply"
              />
            </span>
            <Button
              icon="mdi mdi-delete-outline"
              :label="t('meetings.drafts.discard')"
              severity="contrast"
              text
              :disabled="busy"
              data-testid="draft-discard"
              @click="askDiscard"
            />
          </template>
        </template>
        <template #handbook>
          <HelpButton rounded slug="workspace/meeting" />
        </template>
      </ControlsBar>
    </template>

    <div v-if="loading && !draft" class="state-center" />
    <div v-else-if="notFound" class="state-center state-message" data-testid="draft-not-found">
      <i class="mdi mdi-alert-circle-outline state-icon" aria-hidden="true" />
      <span>{{ t('meetings.drafts.notFound') }}</span>
    </div>
    <div v-else-if="loadError" class="state-center state-message">
      <i class="mdi mdi-alert-outline state-icon" aria-hidden="true" />
      <span>{{ t('meetings.errors.load') }}</span>
    </div>

    <div v-else-if="draft && review" class="draft-page">
      <Message severity="info" data-testid="draft-notice">{{ t('meetings.drafts.notice') }}</Message>
      <Message v-if="draft.review_note" severity="warn" data-testid="draft-review-note">
        <strong>{{ t('meetings.drafts.agentNote') }}</strong>
        {{ draft.review_note }}
      </Message>

      <SectionCard :title="t('meetings.drafts.meeting')" icon="mdi mdi-calendar-account-outline">
        <div v-if="review.newMeeting" class="form-grid">
          <div class="field">
            <label for="draft-meeting-name">{{ t('meetings.drafts.name') }}</label>
            <InputText
              id="draft-meeting-name"
              v-model="review.newMeeting.name"
              maxlength="200"
              :invalid="!!nameError"
              fluid
            />
            <small v-if="nameError" class="p-error">{{ nameError }}</small>
          </div>
          <div class="field">
            <label for="draft-meeting-location">{{ t('meetings.drafts.location') }}</label>
            <InputText id="draft-meeting-location" v-model="review.newMeeting.location" maxlength="200" fluid />
          </div>
          <div class="field">
            <span class="field-label">{{ t('meetings.drafts.when') }}</span>
            <span>{{ formatMeetingWhen(review.newMeeting.starts_at, review.newMeeting.ends_at) }}</span>
            <small class="field-hint">{{ t('meetings.drafts.whenHint') }}</small>
          </div>
        </div>
        <div v-else class="field">
          <span class="field-label">{{ t('meetings.drafts.addsToLabel') }}</span>
          <RouterLink :to="backPath" data-testid="draft-target-meeting">
            {{ draft.meeting_number }} · {{ draft.meeting_name }}
          </RouterLink>
        </div>
        <div v-if="nextMeeting" class="field next-meeting">
          <span class="field-label">{{ t('meetings.drafts.nextMeeting') }}</span>
          <span>
            {{ nextMeeting }}<template v-if="review.next_meeting_location"> · {{ review.next_meeting_location }}</template>
          </span>
          <small v-if="!review.newMeeting" class="field-hint">{{ t('meetings.drafts.nextMeetingHint') }}</small>
        </div>
      </SectionCard>

      <SectionCard
        :title="t('meetings.drafts.people')"
        icon="mdi mdi-account-multiple-outline"
        :hint="t('meetings.drafts.peopleHint')"
      >
        <MeetingNotesDraftPeople v-model="review.people" :matches="draft.people" :attendee-names="attendeeNames" />
      </SectionCard>

      <SectionCard
        :title="t('meetings.drafts.cards')"
        icon="mdi mdi-note-text-outline"
        :hint="t('meetings.drafts.cardsHint')"
      >
        <template #title-end>
          <Tag
            :value="t('meetings.drafts.cardCount', { kept: keptCards, total: review.cards.length })"
            severity="secondary"
          />
        </template>
        <div class="cards">
          <MeetingNotesDraftCardForm
            v-for="(_, index) in review.cards"
            :key="index"
            v-model="review.cards[index]!"
            :index="index"
            :people="review.people"
            :person-label="personLabel"
          />
        </div>
        <small v-if="submitted && keptCards === 0" class="p-error">{{ t('meetings.drafts.noCardKept') }}</small>
      </SectionCard>
    </div>
  </PageLayout>
</template>

<style scoped lang="scss">
.draft-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 64rem;
  overflow-y: auto;
}

.cards {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.next-meeting {
  margin-top: var(--space-3);
}
</style>
