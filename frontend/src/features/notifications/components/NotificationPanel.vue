<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import type { NotificationResponse } from '../types/notificationTypes'

// The unread notifications in the account drawer. The panel is
// presentational: whoever mounts it (AppHeader) passes the store's list and
// handles the two mutations it emits, and moves on to the page a clicked
// notification links to.
interface Props {
  items: NotificationResponse[]
  loading: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'mark-read': [id: number]
  'mark-all-read': []
  open: [path: string]
}>()

const { t } = useI18n()

const unreadNotifications = computed(() => props.items.filter((n) => !n.is_read))
const unreadCount = computed(() => unreadNotifications.value.length)

// The page a notification links to. A meeting opens through its redirect,
// which finds the meeting's project or product.
function linkOf(notification: NotificationResponse): string | null {
  return notification.meeting_id ? `/meetings/${notification.meeting_id}` : null
}

function onClick(notification: NotificationResponse): void {
  emit('mark-read', notification.id)
  const link = linkOf(notification)
  if (link) emit('open', link)
}
</script>

<template>
  <div class="notification-panel">
    <div class="panel-header">
      <span class="panel-title">{{ t('notifications.title') }}</span>
      <Button
        v-if="unreadCount > 0"
        :label="t('notifications.markAllRead')"
        size="small"
        variant="text"
        class="mark-all-btn"
        @click="emit('mark-all-read')"
      />
    </div>

    <div v-if="loading && items.length === 0" class="panel-empty">
      <i
        class="mdi mdi-loading mdi-spin"
        data-testid="notification-loading-icon"
        aria-hidden="true"
      />
    </div>

    <div v-else-if="unreadNotifications.length === 0" class="panel-empty">
      <i class="mdi mdi-bell-off-outline panel-empty-icon" aria-hidden="true" />
      <span>{{ t('notifications.empty') }}</span>
    </div>

    <ul v-else class="notification-list">
      <li v-for="n in unreadNotifications" :key="n.id" class="notification-item unread">
        <button type="button" class="notification-item-btn" @click="onClick(n)">
          <div class="notification-dot-col">
            <span class="unread-dot" />
          </div>
          <div class="notification-content">
            <div class="notification-title">{{ n.title }}</div>
            <div class="notification-message">{{ n.message }}</div>
            <div class="notification-time">{{ formatISODateTime(n.created_at) }}</div>
          </div>
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped lang="scss">
// Sized by its container (the account drawer), not by itself.
.notification-panel {
  width: 100%;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3) var(--space-3);
  border-bottom: 1px solid var(--p-content-border-color);
  flex-shrink: 0;
}

.panel-title {
  font-size: var(--font-size-md);
}

.mark-all-btn {
  font-size: var(--font-size-xs);
  padding: var(--space-1) var(--space-2);
}

.panel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-6) var(--space-4);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.panel-empty-icon {
  font-size: var(--font-size-2xl);
}

.notification-list {
  list-style: none;
  margin: 0;
  padding: 0;
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

.notification-item {
  border-bottom: 1px solid var(--p-content-border-color);
  transition: background-color 0.15s;

  &:last-child {
    border-bottom: none;
  }

  &:hover {
    background-color: var(--p-content-hover-background);
  }

  &.unread {
    background-color: var(--p-primary-50);

    .p-dark & {
      background-color: color-mix(in srgb, var(--p-primary-500) 10%, transparent);
    }
  }
}

.notification-item-btn {
  display: flex;
  width: 100%;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-3);
  border: none;
  background: none;
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: -2px;
  }
}

.notification-dot-col {
  display: flex;
  align-items: flex-start;
  padding-top: var(--space-1);
  width: 10px;
  flex-shrink: 0;
}

.unread-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--p-primary-500);
  flex-shrink: 0;
}

.notification-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.notification-title {
  font-weight: 600;
  font-size: var(--font-size-sm);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.notification-message {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  line-height: 1.35;
}

.notification-time {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  margin-top: var(--space-1);
}
</style>
