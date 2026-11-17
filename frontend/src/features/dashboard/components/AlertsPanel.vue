<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import PanelLoading from './PanelLoading.vue'
import { useNotificationsStore } from '@/features/notifications'
import { formatISODateTime } from '@/core/utils/dates'

const { t } = useI18n()
const store = useNotificationsStore()
</script>

<template>
  <div class="card alerts-panel">
    <div class="panel-title">
      <i class="mdi mdi-bell-ring-outline" aria-hidden="true" />
      <span>{{ t('dashboard.alerts.title') }}</span>
      <Button
        v-if="store.unreadCount > 0"
        :label="t('dashboard.alerts.markAllRead')"
        size="small"
        variant="text"
        class="mark-all-btn"
        @click="store.markAllRead()"
      />
    </div>

    <PanelLoading
      v-if="store.loading && store.notifications.length === 0"
      class="panel-loading"
    />

    <div v-else-if="store.unreadNotifications.length === 0" class="panel-empty">
      <i class="mdi mdi-bell-off-outline panel-empty-icon" aria-hidden="true" />
      <span>{{ t('dashboard.alerts.empty') }}</span>
    </div>

    <ul v-else class="alerts-list">
      <li v-for="n in store.unreadNotifications" :key="n.id">
        <button type="button" class="alerts-item" @click="store.markRead(n.id)">
          <span class="unread-dot" />
          <div class="alerts-content">
            <div class="alerts-item-title">{{ n.title }}</div>
            <div class="alerts-item-message">{{ n.message }}</div>
            <div class="alerts-item-time">{{ formatISODateTime(n.created_at) }}</div>
          </div>
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped lang="scss">
.alerts-panel {
  gap: var(--space-3);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);

  .mark-all-btn {
    margin-left: auto;
    font-size: var(--font-size-xs);
    padding: var(--space-1) var(--space-2);
  }
}

.panel-loading,
.panel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--p-text-muted-color);
  padding: var(--space-5) 0;
  flex: 1 1 auto;
}

.panel-empty-icon {
  font-size: var(--font-size-2xl);
}

.alerts-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

.alerts-item {
  display: flex;
  width: 100%;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: none;
  border-radius: var(--p-content-border-radius);
  background: none;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.15s;

  &:hover {
    background-color: var(--p-content-hover-background);
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: -2px;
  }
}

.unread-dot {
  flex-shrink: 0;
  margin-top: var(--space-1);
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--p-primary-500);
  box-shadow: 0 0 6px var(--p-primary-500);
}

.alerts-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.alerts-item-title {
  font-weight: 600;
  font-size: var(--font-size-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alerts-item-message {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  line-height: 1.3;
}

.alerts-item-time {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
