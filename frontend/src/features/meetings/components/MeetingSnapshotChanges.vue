<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODate } from '@/core/utils/dates'
import EmptyState from '@/shared/components/EmptyState.vue'
import type { MeetingResponse, MeetingSnapshotResponse } from '../types/meetingResponse'
import { compareSnapshot, countChanges } from '../utils/snapshotChanges'
import type { CardChangeStatus } from '../utils/snapshotChanges'
import MeetingLineDiff from './MeetingLineDiff.vue'
import MeetingScopeChip from './MeetingScopeChip.vue'

/**
 * Changes Since: what changed in the notes since the snapshot, card by card,
 * with the line diff of the text, a changed scope, icon or internal flag,
 * the decisions added and removed and the todos added. Internal cards the
 * snapshot left out stay out of the comparison, and a hint says how many.
 */
const props = defineProps<{ snapshot: MeetingSnapshotResponse; meeting: MeetingResponse }>()

const { t } = useI18n()

const comparison = computed(() => compareSnapshot(props.snapshot, props.meeting))
const counts = computed(() => countChanges(comparison.value))
const anyChange = computed(() => counts.value.added + counts.value.removed + counts.value.changed > 0)

const STATUS_SEVERITY: Record<CardChangeStatus, 'success' | 'danger' | 'warn' | 'secondary'> = {
  added: 'success',
  removed: 'danger',
  changed: 'warn',
  unchanged: 'secondary',
}

function iconLabel(icon: string | null): string {
  return icon ? t(`meetings.scopeIcons.${icon}`) : t('meetings.cardHistory.noIcon')
}
</script>

<template>
  <div class="changes" data-testid="meeting-snapshot-changes">
    <p class="hint summary">
      {{
        anyChange
          ? t('meetings.snapshot.changesSummary', {
              changed: counts.changed,
              added: counts.added,
              removed: counts.removed,
            })
          : t('meetings.snapshot.noChanges')
      }}
    </p>
    <EmptyState v-if="!comparison.cards.length" icon="mdi mdi-note-off-outline" :message="t('meetings.snapshot.noCards')" />
    <article
      v-for="change in comparison.cards"
      :key="change.cardId"
      class="change"
      :data-testid="`meeting-snapshot-change-${change.cardId}`"
      :data-status="change.status"
    >
      <header class="change-head">
        <Tag :value="t(`meetings.snapshot.status.${change.status}`)" :severity="STATUS_SEVERITY[change.status]" />
        <MeetingScopeChip :scope="change.scope" :icon="change.scopeIcon" :internal="change.internal" />
        <span v-if="change.scopeChange" class="hint">
          {{ t('meetings.snapshot.scopeWas', { scope: change.scopeChange.from || t('meetings.card.noScope') }) }}
        </span>
        <span v-if="change.iconChange" class="hint">
          {{ t('meetings.snapshot.iconWas', { icon: iconLabel(change.iconChange.from) }) }}
        </span>
        <span v-if="change.internalChange" class="hint">
          {{ change.internalChange.to ? t('meetings.snapshot.nowInternal') : t('meetings.snapshot.noLongerInternal') }}
        </span>
      </header>
      <MeetingLineDiff v-if="change.status !== 'unchanged' && change.bodyChanged" :lines="change.body" />
      <ul v-if="change.decisionsAdded.length || change.decisionsRemoved.length" class="change-list">
        <li v-for="(text, index) in change.decisionsAdded" :key="`added-${index}`" class="added">
          <i class="mdi mdi-gavel" aria-hidden="true" /> {{ t('meetings.snapshot.decisionAdded', { text }) }}
        </li>
        <li v-for="(text, index) in change.decisionsRemoved" :key="`removed-${index}`" class="removed">
          <i class="mdi mdi-gavel" aria-hidden="true" /> {{ t('meetings.snapshot.decisionRemoved', { text }) }}
        </li>
      </ul>
      <ul v-if="change.todosAdded.length" class="change-list">
        <li v-for="todo in change.todosAdded" :key="todo.id" class="added">
          <i class="mdi mdi-plus-box-outline" aria-hidden="true" />
          {{
            t('meetings.snapshot.todoAdded', {
              title: todo.title,
              owners: todo.owners.map((owner) => owner.name).join(', ') || t('meetings.todos.noOwner'),
              due: todo.due_date ? formatISODate(todo.due_date) : t('meetings.todos.noDue'),
            })
          }}
        </li>
      </ul>
    </article>
    <p v-if="comparison.internalLeftOut" class="hint" data-testid="meeting-snapshot-internal-left-out">
      {{ t('meetings.snapshot.internalLeftOut', { count: comparison.internalLeftOut }, comparison.internalLeftOut) }}
    </p>
    <p v-if="!comparison.withTodos" class="hint">{{ t('meetings.snapshot.todosLeftOut') }}</p>
  </div>
</template>

<style scoped lang="scss">
.changes {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.summary {
  margin: 0;
}

.change {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
}

.change-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.change-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);

  .added {
    color: var(--p-green-600);
  }

  .removed {
    color: var(--p-red-600);
    text-decoration: line-through;
  }
}
</style>
