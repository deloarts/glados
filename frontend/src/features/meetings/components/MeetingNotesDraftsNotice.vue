<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import type { MeetingNotesDraftSummaryResponse } from '../types/meetingNotesDraft'

/**
 * Tells the signed-in user which drafts of meeting notes an AI agent
 * prepared for them wait here for review, each with a link to its review.
 * Other users never see a draft, so the notice shows only to its creator.
 */
defineProps<{ drafts: MeetingNotesDraftSummaryResponse[] }>()

const { t } = useI18n()
</script>

<template>
  <Message v-if="drafts.length" severity="info" icon="mdi mdi-robot-outline" data-testid="meeting-drafts-notice">
    <span>{{ t('meetings.drafts.waiting', { count: drafts.length }, drafts.length) }}</span>
    <ul class="draft-links">
      <li v-for="draft in drafts" :key="draft.id">
        <RouterLink :to="`/meeting-notes-drafts/${draft.id}`" :data-testid="`meeting-draft-link-${draft.id}`">
          {{ draft.name ?? t('meetings.drafts.title') }}
        </RouterLink>
        <span class="draft-meta">
          {{ t('meetings.drafts.linkMeta', { cards: draft.card_count, at: formatISODateTime(draft.created) }) }}
        </span>
      </li>
    </ul>
  </Message>
</template>

<style scoped lang="scss">
.draft-links {
  margin: var(--space-1) 0 0;
  padding-left: var(--space-4);
}

.draft-meta {
  margin-left: var(--space-2);
  color: var(--p-text-muted-color);
  font-size: 0.875em;
}
</style>
