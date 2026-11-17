<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

import { useUsersStore } from '@/core/stores/usersStore'
import { choiceOf } from '../utils/meetingNotesDraft'
import type { PersonChoice } from '../utils/meetingNotesDraft'
import type { PersonMatchResponse } from '../types/meetingNotesDraft'

/**
 * The names a draft of meeting notes carries, each matched once to a user,
 * a contact, a guest as written or nobody. Glados preselects the one user
 * or contact that fits a name; a name nothing fits starts as a guest when
 * it is an attendee and as left out when only a todo names it. Any active
 * user can be picked as well.
 */
const people = defineModel<Record<string, PersonChoice>>({ required: true })
const props = defineProps<{
  matches: PersonMatchResponse[]
  /** The names that attend, which may stay guests. */
  attendeeNames: Set<string>
}>()

const { t } = useI18n()
const usersStore = useUsersStore()
onMounted(() => void usersStore.ensureLoaded())

interface Option {
  value: PersonChoice
  label: string
}
interface Group {
  label: string
  items: Option[]
}

function groupsFor(match: PersonMatchResponse): Group[] {
  const suggested = match.candidates.map((candidate) => ({
    value: choiceOf(candidate),
    label: `${candidate.name} · ${t(`meetings.drafts.kinds.${candidate.kind}`)}`,
  }))
  const taken = new Set(suggested.map((option) => option.value))
  const users = usersStore.users
    .filter((user) => user.is_active && !user.is_systemuser && !user.is_service_account)
    .map((user) => ({ value: `user:${user.id}` as PersonChoice, label: user.full_name }))
    .filter((option) => !taken.has(option.value))
  const other: Option[] = [
    ...(props.attendeeNames.has(match.written)
      ? [{ value: 'guest' as const, label: t('meetings.drafts.asGuest', { name: match.written }) }]
      : []),
    { value: 'none', label: t('meetings.drafts.leaveOut') },
  ]
  return [
    ...(suggested.length ? [{ label: t('meetings.drafts.suggested'), items: suggested }] : []),
    { label: t('meetings.drafts.other'), items: other },
    ...(users.length ? [{ label: t('meetings.drafts.allUsers'), items: users }] : []),
  ]
}

const rows = computed(() => props.matches.map((match) => ({ match, groups: groupsFor(match) })))
</script>

<template>
  <p v-if="!matches.length" class="empty-note">{{ t('meetings.drafts.noPeople') }}</p>
  <div v-else class="people">
    <div v-for="{ match, groups } in rows" :key="match.written" class="person-row" data-testid="draft-person">
      <span class="written">
        {{ match.written }}
        <Tag
          v-if="!match.best"
          :value="match.candidates.length ? t('meetings.drafts.ambiguous') : t('meetings.drafts.noMatch')"
          severity="warn"
        />
      </span>
      <Select
        v-model="people[match.written]"
        :options="groups"
        option-group-label="label"
        option-group-children="items"
        option-label="label"
        option-value="value"
        filter
        fluid
        :aria-label="t('meetings.drafts.matchFor', { name: match.written })"
        :data-testid="`draft-person-select-${match.written}`"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.people {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.person-row {
  display: grid;
  grid-template-columns: minmax(10rem, 16rem) minmax(12rem, 24rem);
  align-items: center;
  gap: var(--space-3);
}

.written {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-weight: 600;
}
</style>
