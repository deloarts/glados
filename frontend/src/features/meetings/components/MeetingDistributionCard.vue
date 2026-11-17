<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import EmptyState from '@/shared/components/EmptyState.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import type { MeetingDistributionEntryResponse } from '../types/meetingResponse'

/**
 * The Distribution card: every print, download and send of the notes with
 * who did it, when, the issue it carried and, for a send, its recipients.
 * The actions on an entry, such as viewing what went out, come in through
 * the `actions` slot.
 */
defineProps<{ entries: MeetingDistributionEntryResponse[] }>()

defineSlots<{
  actions?: (props: { entry: MeetingDistributionEntryResponse }) => unknown
}>()

const { t } = useI18n()

const ICONS = {
  sent: 'mdi mdi-email-fast-outline',
  printed: 'mdi mdi-printer-outline',
  downloaded: 'mdi mdi-download-outline',
} as const

function summary(entry: MeetingDistributionEntryResponse): string {
  if (entry.kind === 'sent') return t('meetings.distribution.sentTo', { recipients: entry.recipients.join(', ') })
  return t(`meetings.distribution.${entry.kind}`)
}
</script>

<template>
  <SectionCard
    :title="t('meetings.distribution.title')"
    icon="mdi-email-arrow-right-outline"
    data-testid="meeting-distribution-card"
  >
    <ul v-if="entries.length" class="entries">
      <li v-for="entry in entries" :key="entry.journal_entry_id" class="entry" data-testid="meeting-distribution-entry">
        <i :class="ICONS[entry.kind]" aria-hidden="true" />
        <div class="entry-text">
          <span>{{ summary(entry) }}</span>
          <small class="text-muted">
            {{ entry.actor_full_name }} · {{ formatISODateTime(entry.at) }} · {{ entry.issue.revision }}
          </small>
          <small v-if="entry.cc.length" class="text-muted">
            {{ t('meetings.distribution.cc', { recipients: entry.cc.join(', ') }) }}
          </small>
          <span v-if="$slots.actions" class="entry-actions">
            <slot name="actions" :entry="entry" />
          </span>
        </div>
      </li>
    </ul>
    <EmptyState v-else icon="mdi mdi-email-outline" :message="t('meetings.distribution.empty')" />
  </SectionCard>
</template>

<style scoped lang="scss">
.entries {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.entry {
  display: flex;
  gap: var(--space-2);
}

.entry-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.entry-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
</style>
