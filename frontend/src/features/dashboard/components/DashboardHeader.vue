<script setup lang="ts">
import { computed } from 'vue'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import { getDisplayTimezone, localeTag, minutesSinceMidnight, todayStart } from '@/core/utils/dates'
import { tmStringArray } from '@/core/i18n/tmStringArray'
import { pickDailyMessage } from '../utils/dailyGreeting'

const userStore = useCurrentUserStore()
const brandingStore = usePublicBrandingStore()

// Time of day on the tenant's clock picks the bucket, and pickDailyMessage
// rotates its phrasings per day.
const greetingBucket = computed(() => {
  const now = new Date()
  const minutes = minutesSinceMidnight(now, getDisplayTimezone()) ?? now.getHours() * 60
  const hour = Math.floor(minutes / 60)
  if (hour < 5) return 'evening'
  if (hour < 12) return 'morning'
  if (hour < 18) return 'afternoon'
  return 'evening'
})

const greeting = computed(() =>
  pickDailyMessage(tmStringArray(`dashboard.greeting.${greetingBucket.value}`), todayStart()),
)

const firstName = computed(() => userStore.user?.full_name.split(' ')[0] ?? '')

const today = computed(() =>
  new Date().toLocaleDateString(localeTag(), {
    timeZone: getDisplayTimezone(),
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }),
)
</script>

<template>
  <div class="card dashboard-header">
    <div class="dashboard-header-text">
      <h1 class="dashboard-header-greeting">
        {{ greeting }}<template v-if="firstName">, {{ firstName }}</template>
      </h1>
      <span class="dashboard-header-subtitle">{{ today }} · {{ brandingStore.appName }}</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
// Uses .card, overriding only its height: 100%, which would claim the whole
// viewport in the dashboard column.
.dashboard-header {
  height: auto;
  padding: var(--space-4) var(--space-4);
}

.dashboard-header-text {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.dashboard-header-greeting {
  font-size: var(--font-size-2xl);
  margin: 0;
}

.dashboard-header-subtitle {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}
</style>
