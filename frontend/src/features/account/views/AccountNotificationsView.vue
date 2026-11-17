<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { HelpButton } from '@/shared/help'
import { useNotificationsStore } from '@/features/notifications'
import { formatISODateTime } from '@/core/utils/dates'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useDateRangeTupleFilter } from '@/shared/composables/useDateRangeFilter'
import type { DateRangeTuple } from '@/shared/composables/useDateRangeFilter'

const { t } = useI18n()
const store = useNotificationsStore()

watchLoadingBar(() => store.loading)

// The notifications endpoint takes no query params and the store holds the
// whole list, so the date range filters client-side.
const dateRange = ref<DateRangeTuple>([null, null])
const { getDateRangeModel, setDateRangeModel } = useDateRangeTupleFilter(dateRange)
const dateRangeModel = computed(getDateRangeModel)

const hasActiveFilters = computed(() => dateRange.value[0] !== null || dateRange.value[1] !== null)

function clearFilters(): void {
  dateRange.value = [null, null]
}

const visibleNotifications = computed(() => {
  const [from, to] = dateRange.value
  if (from === null && to === null) return store.notifications

  const fromMs = from ? new Date(from).setHours(0, 0, 0, 0) : null
  // The picker hands back midnight for the end date: a single-day range would
  // match nothing without stretching it to the end of that day.
  const toMs = to ? new Date(to).setHours(23, 59, 59, 999) : null

  return store.notifications.filter((n) => {
    const created = new Date(n.created_at).getTime()
    if (fromMs !== null && created < fromMs) return false
    if (toMs !== null && created > toMs) return false
    return true
  })
})

onMounted(() => store.refresh())
</script>

<template>
  <PageLayout>
    <template #controls>
      <Toolbar>
        <template #start>
          <Button
            :label="t('notifications.markAllRead')"
            icon="mdi mdi-check-all"
            severity="contrast"
            text
            :disabled="store.unreadCount === 0"
            @click="store.markAllRead()"
          />
        </template>
        <template #end>
          <HelpButton slug="account/notifications" rounded />
        </template>
      </Toolbar>
    </template>
    <template #views>
      <ViewsBar
        id-prefix="notifications"
        hide-views-toggle
        :syncing="store.loading"
        :has-active-filters="hasActiveFilters"
        @sync="store.refresh()"
        @clear="clearFilters()"
      >
        <template #start-extra>
          <DatePicker
            :model-value="dateRangeModel"
            selection-mode="range"
            show-button-bar
            show-clear
            size="small"
            :placeholder="t('notifications.filters.dateRange')"
            @update:model-value="setDateRangeModel"
            @clear-click="clearFilters()"
          />
        </template>
      </ViewsBar>
    </template>

    <div v-if="visibleNotifications.length === 0" class="panel-empty">
      <i class="mdi mdi-bell-off-outline panel-empty-icon" aria-hidden="true" />
      <span>{{
        hasActiveFilters ? t('notifications.filters.empty') : t('notifications.empty')
      }}</span>
    </div>

    <ul v-else class="notification-list">
      <li v-for="n in visibleNotifications" :key="n.id" class="notification-item" :class="{ unread: !n.is_read }">
        <button
          type="button"
          class="notification-item-btn"
          :disabled="n.is_read"
          @click="store.markRead(n.id)"
        >
          <div class="notification-dot-col">
            <span v-if="!n.is_read" class="unread-dot" />
          </div>
          <div class="notification-content">
            <div class="notification-title">{{ n.title }}</div>
            <div class="notification-message">{{ n.message }}</div>
            <div class="notification-time">{{ formatISODateTime(n.created_at) }}</div>
          </div>
        </button>
      </li>
    </ul>
  </PageLayout>
</template>

<style scoped lang="scss">
// Rows carry their own padding, so the card only provides surface and
// border.
:deep(.card) {
  padding: 0;
  overflow: hidden;
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
  overflow-y: auto;
}

.notification-item {
  border-bottom: 1px solid var(--p-content-border-color);
  transition: background-color 0.15s;

  &:last-child {
    border-bottom: none;
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
  padding: var(--space-3);
  border: none;
  background: none;
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: default;

  &:not(:disabled) {
    cursor: pointer;

    &:hover {
      background-color: var(--p-content-hover-background);
    }
  }

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
