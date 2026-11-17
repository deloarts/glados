<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODate, formatISODateTime } from '@/core/utils/dates'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import { formatMeetingWhen } from '../utils/meetingDates'
import { meetingNotesTabPath } from '../utils/meetingRoutes'
import type { MeetingResponse } from '../types/meetingResponse'

/**
 * The identity strip of a meeting: its number, Valid or Invalid, its name,
 * date and times, location, the project or product it belongs to, the
 * meeting it follows up, whether the notes were sent or printed, and its
 * tags.
 */
const props = defineProps<{ meeting: MeetingResponse | null }>()

const { t } = useI18n()

const ownerLabel = computed(() => {
  const owner = props.meeting?.owner
  if (!owner) return ''
  return owner.kind === 'project'
    ? t('meetings.info.projectOwner', { number: owner.number })
    : t('meetings.info.productOwner', { number: owner.number })
})
</script>

<template>
  <InfoBar>
    <template v-if="meeting">
      <span class="info-title" data-testid="meeting-info-number">{{ meeting.meeting_number }}</span>
      <span class="info-sep" />
      <Tag
        :value="meeting.valid ? t('meetings.valid') : t('meetings.invalid')"
        :severity="meeting.valid ? 'success' : 'danger'"
        data-testid="meeting-info-validity"
      />
      <Tag
        v-if="meeting.last_sent_at"
        v-tooltip.bottom="t('meetings.info.lastSent', { at: formatISODateTime(meeting.last_sent_at) })"
        :value="t('meetings.info.sent', { date: formatISODate(meeting.last_sent_at) })"
        icon="mdi mdi-email-fast-outline"
        severity="info"
      />
      <Tag
        v-if="meeting.last_printed_at"
        v-tooltip.bottom="t('meetings.info.lastPrinted', { at: formatISODateTime(meeting.last_printed_at) })"
        :value="t('meetings.info.printed')"
        icon="mdi mdi-printer-outline"
        severity="secondary"
      />
      <span class="info-sep" />
      <span class="info-name" data-testid="meeting-info-name">{{ meeting.name }}</span>
      <span class="info-sep" />
      <span class="info-muted">
        <i class="mdi mdi-calendar-clock" aria-hidden="true" />
        {{ formatMeetingWhen(meeting.starts_at, meeting.ends_at) }}
      </span>
      <template v-if="meeting.location">
        <span class="info-sep" />
        <span class="info-muted">
          <i class="mdi mdi-map-marker-outline" aria-hidden="true" />
          {{ meeting.location }}
        </span>
      </template>
      <span class="info-sep" />
      <span class="info-muted">
        <i class="mdi mdi-folder" aria-hidden="true" />
        <RouterLink :to="meetingNotesTabPath(meeting.owner)" class="info-link" data-testid="meeting-info-owner">
          {{ ownerLabel }}
        </RouterLink>
      </span>
      <template v-if="meeting.follow_up_of">
        <span class="info-sep" />
        <span class="info-muted">
          <i class="mdi mdi-arrow-u-left-top" aria-hidden="true" />
          <RouterLink
            :to="`/meetings/${meeting.follow_up_of.id}`"
            class="info-link"
            data-testid="meeting-info-follow-up-of"
          >
            {{ t('meetings.info.followUpOf', { number: meeting.follow_up_of.meeting_number }) }}
          </RouterLink>
        </span>
      </template>
      <template v-if="meeting.tags.length">
        <span class="info-sep" />
        <span class="info-tags" data-testid="meeting-info-tags">
          <Tag v-for="tag in meeting.tags" :key="tag" :value="tag" icon="mdi mdi-tag-outline" severity="secondary" />
        </span>
      </template>
    </template>
  </InfoBar>
</template>

<style scoped lang="scss">
.info-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.info-name {
  font-size: var(--font-size-lg);
}

.info-muted {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

.info-link {
  color: inherit;
}

.info-tags {
  display: inline-flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
</style>
