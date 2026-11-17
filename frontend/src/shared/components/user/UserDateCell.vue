<script setup lang="ts">
import { computed } from 'vue'

import { useUsersStore } from '@/core/stores/usersStore'
import { formatDateOrDash, formatDateTimeOrEmpty, formatISODateTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import UserAvatarPreview from './UserAvatarPreview.vue'

interface PreviewUser {
  id: number
  username: string
  full_name: string
  email?: string
  has_avatar: boolean
}

/**
 * A table cell for when something happened and who did it, in two lines:
 * the date, its time in the tooltip, and below it the person in muted text,
 * whose card opens on hover. The person comes from the user list by id, or
 * from the user the record embeds; when neither is there the name alone is
 * shown, and without any of them the second line shows the empty
 * placeholder. Without a date the cell shows the empty placeholder alone.
 */
const props = defineProps<{
  date: string | null | undefined
  userId?: number | null
  /** The user the record embeds, such as its creator, for when the user list has no entry. */
  user?: PreviewUser | null
  /** The person's name as the record keeps it, for when the user list has no entry. */
  name?: string | null
  /** Shows the time with the date, for a moment such as the last change. */
  withTime?: boolean
}>()

const users = useUsersStore()
void users.ensureLoaded()

const shownUser = computed(() => {
  const id = props.userId ?? props.user?.id ?? null
  return (id != null ? users.getById(id) : undefined) ?? props.user ?? null
})
const shown = computed(() => {
  if (!props.date) return null
  return props.withTime ? formatISODateTime(props.date) : formatDateOrDash(props.date)
})
</script>

<template>
  <div v-if="shown" class="user-date-cell">
    <span :title="formatDateTimeOrEmpty(date)">{{ shown }}</span>
    <UserAvatarPreview v-if="shownUser" :user="shownUser" name-only class="actor" />
    <span v-else-if="name" class="actor">{{ name }}</span>
    <span v-else class="actor">{{ getEmptyPlaceholder() }}</span>
  </div>
  <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
</template>

<style scoped lang="scss">
.user-date-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

// The muted second line of the two-line cells, as in the lots table.
.actor {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
