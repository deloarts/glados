<script setup lang="ts">
import { computed, ref } from 'vue'
import Popover from 'openvue/popover'

import UserAvatar from './UserAvatar.vue'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

// A user embedded in another resource carries no e-mail address, only the
// full user view of user administration does, so the card shows the mail
// line only when one is there.
interface PreviewUser {
  id: number
  username: string
  full_name: string
  email?: string
  has_avatar: boolean
}

const props = withDefaults(
  defineProps<{
    user: PreviewUser | null
    showName?: boolean
    /** Just the name, which opens the card on hover, for a muted line in a table cell. */
    nameOnly?: boolean
  }>(),
  { showName: true, nameOnly: false },
)

const popover = ref()
let hideTimeout: ReturnType<typeof setTimeout> | null = null

function initialsOf(user: PreviewUser): string {
  return user.full_name
    .split(' ')
    .map((p) => p[0] ?? '')
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

const initials = computed(() => (props.user ? initialsOf(props.user) : ''))

function clearHideTimeout(): void {
  if (hideTimeout) {
    clearTimeout(hideTimeout)
    hideTimeout = null
  }
}

function onEnter(event: MouseEvent): void {
  clearHideTimeout()
  popover.value?.show(event)
}

function onLeave(): void {
  clearHideTimeout()
  hideTimeout = setTimeout(() => {
    popover.value?.hide()
  }, 150)
}
</script>

<template>
  <span v-if="user" class="user-avatar-preview">
    <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions, vuejs-accessibility/mouse-events-have-key-events -- the hover card is a mouse convenience, the name is on screen -->
    <span v-if="nameOnly" class="user-avatar-preview-name" @mouseenter="onEnter" @mouseleave="onLeave">{{
      user.full_name
    }}</span>
    <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions, vuejs-accessibility/mouse-events-have-key-events -- the hover card is a mouse convenience, the name is on screen or the bubble's accessible name -->
    <span
      v-else
      class="user-avatar-preview-bubble"
      :role="showName ? undefined : 'img'"
      :aria-label="showName ? undefined : user.full_name"
      @mouseenter="onEnter"
      @mouseleave="onLeave"
    >
      <UserAvatar
        :user-id="user.id"
        :has-avatar="user.has_avatar"
        img-class="user-avatar-preview-img"
      >
        <span class="user-avatar-preview-initials">{{ initials }}</span>
      </UserAvatar>
    </span>
    <span v-if="showName && !nameOnly">{{ user.full_name }}</span>

    <Popover ref="popover">
      <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions, vuejs-accessibility/mouse-events-have-key-events -- keeps the hover card open while the mouse is on it -->
      <div class="user-avatar-preview-card" @mouseenter="clearHideTimeout" @mouseleave="onLeave">
        <span class="user-avatar-preview-card-bubble">
          <UserAvatar
            :user-id="user.id"
            :has-avatar="user.has_avatar"
            img-class="user-avatar-preview-card-img"
          >
            <span class="user-avatar-preview-initials">{{ initials }}</span>
          </UserAvatar>
        </span>
        <div>
          <div class="user-avatar-preview-card-row">
            <i class="mdi mdi-tag" aria-hidden="true" />
            <span>{{ user.username }}</span>
          </div>
          <div class="user-avatar-preview-card-row">
            <i class="mdi mdi-account" aria-hidden="true" />
            <span>{{ user.full_name }}</span>
          </div>
          <div v-if="user.email" class="user-avatar-preview-card-row">
            <i class="mdi mdi-email-outline" aria-hidden="true" />
            <a :href="`mailto:${user.email}`" class="user-avatar-preview-mail">{{ user.email }}</a>
          </div>
        </div>
      </div>
    </Popover>
  </span>
  <span v-else>{{ getEmptyPlaceholder() }}</span>
</template>

<style scoped>
i {
  font-size: var(--font-size-sm);
}

.user-avatar-preview {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.user-avatar-preview-name {
  cursor: default;
}

.user-avatar-preview-bubble {
  flex-shrink: 0;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  overflow: hidden;
  background-color: var(--p-primary-500);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: default;
}

.user-avatar-preview-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-avatar-preview-initials {
  font-size: var(--font-size-xs);
  font-weight: 700;
  color: var(--on-accent);
  letter-spacing: 0.03em;
}

.user-avatar-preview-card {
  min-width: 14rem;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
}

.user-avatar-preview-card-bubble {
  width: 3.5rem;
  height: 3.5rem;
  border-radius: 50%;
  overflow: hidden;
  background-color: var(--p-primary-500);
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-avatar-preview-card-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-avatar-preview-card-bubble .user-avatar-preview-initials {
  font-size: var(--font-size-lg);
}

.user-avatar-preview-mail {
  color: var(--p-primary-color);
  text-decoration: none;
}

.user-avatar-preview-mail:hover {
  text-decoration: underline;
}

.user-avatar-preview-card-row {
  width: 100%;
  display: flex;
  gap: var(--space-3);
  align-items: baseline;
  flex-direction: row;
  padding-left: var(--space-4);
}
</style>
