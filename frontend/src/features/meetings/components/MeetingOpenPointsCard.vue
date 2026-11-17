<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { formatISODate, todayKey } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import { setMeetingTodoDone } from '../api/meetingsApi'
import type { MeetingOpenPointResponse } from '../types/meetingResponse'

/**
 * The Open Points card of a follow-up meeting: the open todos of the meeting
 * it follows and of that meeting's own predecessors, each with a link to its
 * card. Ticking one off here ticks the original todo off.
 */
const props = defineProps<{
  points: MeetingOpenPointResponse[]
  canWrite: boolean
  writeBlocked: string
}>()

const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()
const toast = useAppToast()
const currentUserStore = useCurrentUserStore()
const busy = ref<Set<number>>(new Set())
const today = todayKey()

const groups = computed(() => {
  const byMeeting = new Map<number, { label: string; points: MeetingOpenPointResponse[] }>()
  for (const point of props.points) {
    const group = byMeeting.get(point.meeting.id) ?? {
      label: `${point.meeting.meeting_number} · ${point.meeting.name} · ${formatISODate(point.meeting_starts_at)}`,
      points: [],
    }
    group.points.push(point)
    byMeeting.set(point.meeting.id, group)
  }
  return [...byMeeting.entries()].map(([id, group]) => ({ id, ...group }))
})

function canTick(point: MeetingOpenPointResponse): boolean {
  const userId = currentUserStore.user?.id
  return props.canWrite || point.todo.owners.some((owner) => owner.user?.id === userId)
}

async function tick(point: MeetingOpenPointResponse): Promise<void> {
  busy.value = new Set(busy.value).add(point.todo.id)
  try {
    await setMeetingTodoDone(point.meeting.id, point.todo.id, true)
    toast.success(point.todo.title, t('meetings.openPoints.ticked'))
    emit('changed')
  } catch (err) {
    toast.error(point.todo.title, extractApiError(err) ?? t('meetings.errors.unknown'))
  } finally {
    const next = new Set(busy.value)
    next.delete(point.todo.id)
    busy.value = next
  }
}
</script>

<template>
  <SectionCard
    :title="t('meetings.openPoints.title')"
    :hint="t('meetings.openPoints.hint')"
    icon="mdi-format-list-checks"
    data-testid="meeting-open-points"
  >
    <div v-if="groups.length" class="groups">
      <div v-for="group in groups" :key="group.id" class="group">
        <span class="group-label">{{ group.label }}</span>
        <ul class="points">
          <li v-for="point in group.points" :key="point.todo.id" class="point">
            <span v-tooltip.top="canTick(point) ? undefined : writeBlocked || undefined">
              <Checkbox
                :model-value="false"
                binary
                :input-id="`open-point-${point.todo.id}`"
                :disabled="!canTick(point) || busy.has(point.todo.id)"
                :aria-label="t('meetings.todos.markDone')"
                :data-testid="`meeting-open-point-${point.todo.id}`"
                @update:model-value="tick(point)"
              />
            </span>
            <span class="point-text">
              <label :for="`open-point-${point.todo.id}`">{{ point.todo.title }}</label>
              <small class="text-muted">
                {{ point.todo.owners.map((owner) => owner.name).join(', ') || t('meetings.todos.noOwner') }}
                <template v-if="point.todo.due_date">
                  ·
                  <span :class="{ overdue: point.todo.due_date < today }">{{ formatISODate(point.todo.due_date) }}</span>
                </template>
              </small>
            </span>
            <RouterLink
              :to="`/meetings/${point.meeting.id}#card-${point.todo.card_id}`"
              class="point-link"
              :aria-label="t('meetings.openPoints.openCard', { scope: point.card_scope || t('meetings.card.noScope') })"
            >
              {{ point.card_scope || t('meetings.card.noScope') }}
            </RouterLink>
          </li>
        </ul>
      </div>
    </div>
    <p v-else class="empty-note">{{ t('meetings.openPoints.none') }}</p>
  </SectionCard>
</template>

<style scoped lang="scss">
.groups {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.group-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.points {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.point {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
}

.point-text {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-width: 0;
}

.point-link {
  color: inherit;
  font-size: var(--font-size-sm);
  white-space: nowrap;

  &:hover {
    color: var(--p-primary-color);
  }
}

.overdue {
  color: var(--p-red-500);
  font-weight: 600;
}
</style>
