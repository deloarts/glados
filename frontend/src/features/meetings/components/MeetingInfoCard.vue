<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { formatISODateTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { extractApiError } from '@/core/utils/errors'
import ContactLinks from '@/shared/components/ContactLinks.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { anonymiseMeetingAttendee } from '../api/meetingsApi'
import { formatNextMeeting } from '../utils/meetingDates'
import type { MeetingAttendeeResponse, MeetingResponse } from '../types/meetingResponse'

/**
 * The Meeting card beside the notes: the attendees with their e-mail
 * address and a tag for their status, the location, the next meeting when
 * one is agreed and who created the meeting. A manager can blank a guest's
 * name and e-mail address.
 */
const props = defineProps<{ meeting: MeetingResponse }>()
const emit = defineEmits<{ updated: [meeting: MeetingResponse] }>()

const { t } = useI18n()
const toast = useAppToast()
const confirm = useConfirm()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()

const canManage = computed(() => hasPermission(Permission.MANAGE_MEETINGS))

const STATUS_SEVERITIES = {
  present: 'success',
  excused: 'warn',
  distribution_only: 'secondary',
} as const

const nextMeeting = computed(() =>
  formatNextMeeting(props.meeting.next_meeting_date, props.meeting.next_meeting_time),
)

const KIND_ICONS = {
  user: 'mdi mdi-account-outline',
  contact: 'mdi mdi-card-account-mail-outline',
  guest: 'mdi mdi-account-question-outline',
} as const

function askAnonymise(attendee: MeetingAttendeeResponse): void {
  confirm.require({
    header: t('meetings.info.anonymiseHeader'),
    message: t('meetings.info.anonymiseConfirm', { name: attendee.name }),
    icon: 'mdi mdi-account-off-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary', text: true },
    acceptProps: { label: t('meetings.info.anonymise'), severity: 'danger', icon: 'mdi mdi-account-off-outline' },
    accept: () => void runAnonymise(attendee),
  })
}

async function runAnonymise(attendee: MeetingAttendeeResponse): Promise<void> {
  try {
    emit('updated', await anonymiseMeetingAttendee(props.meeting.id, attendee.id))
    toast.success(props.meeting.meeting_number, t('meetings.info.anonymised'))
  } catch (err) {
    toast.error(props.meeting.meeting_number, extractApiError(err) ?? t('meetings.errors.unknown'))
  }
}
</script>

<template>
  <SectionCard :title="t('meetings.info.title')" icon="mdi-account-group-outline" data-testid="meeting-info-card">
    <dl class="facts">
      <dt class="field-label">{{ t('meetings.info.attendees') }}</dt>
      <dd>
        <ul v-if="meeting.attendees.length" class="attendees">
          <li v-for="attendee in meeting.attendees" :key="attendee.id" class="attendee" data-testid="meeting-info-attendee">
            <UserAvatarPreview v-if="attendee.user" :user="attendee.user" :show-name="false" />
            <span v-else class="kind-icon"><i :class="KIND_ICONS[attendee.kind]" aria-hidden="true" /></span>
            <span class="attendee-name">
              <span :class="{ 'text-muted': attendee.anonymised }">
                {{ attendee.anonymised ? t('meetings.attendees.anonymised') : attendee.name }}
              </span>
              <ContactLinks v-if="!attendee.anonymised" :email="attendee.email" class="attendee-email" />
            </span>
            <Tag
              :value="t(`meetings.attendees.status.${attendee.status}`)"
              :severity="STATUS_SEVERITIES[attendee.status]"
              data-testid="meeting-info-attendee-status"
            />
            <span
              v-if="attendee.kind === 'guest' && !attendee.anonymised"
              v-tooltip.top="missing(Permission.MANAGE_MEETINGS) || t('meetings.info.anonymise')"
            >
              <Button
                icon="mdi mdi-account-off-outline"
                size="small"
                severity="secondary"
                text
                :disabled="!canManage"
                :aria-label="t('meetings.info.anonymiseGuest', { name: attendee.name })"
                @click="askAnonymise(attendee)"
              />
            </span>
          </li>
        </ul>
        <span v-else class="empty-note">{{ t('meetings.attendees.none') }}</span>
      </dd>

      <dt class="field-label">{{ t('meetings.info.location') }}</dt>
      <dd>{{ meeting.location || getEmptyPlaceholder() }}</dd>

      <template v-if="nextMeeting">
        <dt class="field-label">{{ t('meetings.info.nextMeeting') }}</dt>
        <dd data-testid="meeting-info-next">
          {{ nextMeeting }}<template v-if="meeting.next_meeting_location">, {{ meeting.next_meeting_location }}</template>
        </dd>
      </template>

      <dt class="field-label">{{ t('meetings.info.created') }}</dt>
      <dd>
        {{ meeting.creator?.full_name ?? t('meetings.unknownUser') }} · {{ formatISODateTime(meeting.created) }}
      </dd>
    </dl>
  </SectionCard>
</template>

<style scoped lang="scss">
.facts {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin: 0;

  dd {
    margin: 0 0 var(--space-2);
  }
}

.attendees {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.attendee {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

// As wide as a user's picture, so the names line up.
.kind-icon {
  flex-shrink: 0;
  width: 1.75rem;
  text-align: center;
  color: var(--p-text-muted-color);
}

.attendee-email {
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.attendee-name {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-width: 0;
}
</style>
