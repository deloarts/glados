<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import type { MeetingIssueResponse } from '../types/meetingResponse'

/**
 * The notice that the notes changed since they were last sent: how many
 * cards changed, were added or removed, with Show Changes, which compares
 * them with what was sent, and Send Again. It shows only once the notes
 * were sent and something changed since; ticking a todo off is no change.
 */
const props = defineProps<{
  issue: MeetingIssueResponse | null
  /** An invalid meeting is not sent again, so it offers no Send Again. */
  valid: boolean
  /** Whether the user holds the rights to send. */
  canSend: boolean
  /** Why the user may not send, naming the missing permission. */
  sendBlocked: string
  /** Whether the snapshot of the last send is known, which Show Changes opens. */
  hasSnapshot: boolean
}>()

const emit = defineEmits<{ 'show-changes': []; 'send-again': [] }>()

const { t } = useI18n()

const counts = computed(() => {
  const issue = props.issue
  if (!issue?.last_sent_at) return null
  const changed = issue.changed_card_ids.length
  const added = issue.added_card_ids.length
  const removed = issue.removed_card_ids.length
  return changed + added + removed ? { changed, added, removed, at: formatISODateTime(issue.last_sent_at) } : null
})
</script>

<template>
  <Message v-if="counts" severity="warn" data-testid="meeting-changed-notice">
    <div class="notice">
      <span>{{ t('meetings.changedNotice.text', counts) }}</span>
      <span class="notice-actions">
        <Button
          v-if="hasSnapshot"
          :label="t('meetings.changedNotice.showChanges')"
          icon="mdi mdi-file-compare"
          size="small"
          severity="secondary"
          outlined
          data-testid="meeting-changed-show"
          @click="emit('show-changes')"
        />
        <span v-if="valid" v-tooltip.top="sendBlocked || undefined">
          <Button
            :label="t('meetings.changedNotice.sendAgain')"
            icon="mdi mdi-email-fast-outline"
            size="small"
            severity="secondary"
            outlined
            :disabled="!canSend"
            data-testid="meeting-changed-send"
            @click="emit('send-again')"
          />
        </span>
      </span>
    </div>
  </Message>
</template>

<style scoped lang="scss">
.notice {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-4);
}

.notice-actions {
  display: flex;
  gap: var(--space-2);
}
</style>
