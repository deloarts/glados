<script setup lang="ts">
// Today's and the month's headline figures. Today's block exists only for
// the current month; its worked time and balances arrive already advanced
// to the current minute by the view, so this card only formats them.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISOTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { formatDuration, formatSignedDuration } from '@/shared/utils/formatDuration'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import type { TimeTrackingToday, TimeTrackingTotals } from '../types/timeTrackingTypes'

const props = defineProps<{
  totals: TimeTrackingTotals
  today: TimeTrackingToday | null
  fetchedAt: string
}>()

const { t } = useI18n()

function signedClass(seconds: number | null): string | undefined {
  return seconds !== null && seconds <= -60 ? 'is-negative' : undefined
}

const runningBalance = computed(() => props.today?.running_balance_seconds ?? null)
</script>

<template>
  <SectionCard :title="t('timeTracking.totals.title')" data-testid="time-tracking-totals">
    <template v-if="today">
      <div class="tt-status">
        <Tag
          :value="today.clocked_in ? t('timeTracking.totals.clockedIn') : t('timeTracking.totals.clockedOut')"
          :severity="today.clocked_in ? 'success' : 'secondary'"
          :icon="today.clocked_in ? 'mdi mdi-login' : 'mdi mdi-logout'"
          data-testid="time-tracking-clock-state"
        />
      </div>

      <dl class="tt-figures">
        <div class="tt-figure">
          <dt>{{ t('timeTracking.totals.firstIn') }}</dt>
          <dd data-testid="time-tracking-first-in">
            {{ today.first_in ? formatISOTime(today.first_in) : getEmptyPlaceholder() }}
          </dd>
        </div>
        <div class="tt-figure tt-figure--hero">
          <dt>{{ t('timeTracking.totals.workedToday') }}</dt>
          <dd data-testid="time-tracking-worked-today">{{ formatDuration(today.worked_seconds) }}</dd>
        </div>
        <div class="tt-figure">
          <dt>{{ t('timeTracking.totals.targetToday') }}</dt>
          <dd>{{ formatDuration(today.target_seconds) }}</dd>
        </div>
        <div class="tt-figure">
          <dt>{{ t('timeTracking.totals.dayBalance') }}</dt>
          <dd :class="signedClass(today.day_balance_seconds)" data-testid="time-tracking-day-balance">
            {{ formatSignedDuration(today.day_balance_seconds) }}
          </dd>
        </div>
        <div class="tt-figure">
          <dt>{{ t('timeTracking.totals.runningBalance') }}</dt>
          <dd :class="signedClass(runningBalance)">
            {{ runningBalance === null ? getEmptyPlaceholder() : formatSignedDuration(runningBalance) }}
          </dd>
        </div>
        <div v-if="today.clocked_in && today.target_reached_at" class="tt-figure">
          <dt>{{ t('timeTracking.totals.targetReachedAt') }}</dt>
          <dd>{{ formatISOTime(today.target_reached_at) }}</dd>
        </div>
      </dl>

      <Divider />
    </template>

    <div class="tt-subtitle">{{ t('timeTracking.totals.month') }}</div>
    <dl class="tt-figures">
      <div class="tt-figure">
        <dt>{{ t('timeTracking.totals.worked') }}</dt>
        <dd data-testid="time-tracking-month-worked">{{ formatDuration(totals.worked_seconds) }}</dd>
      </div>
      <div class="tt-figure">
        <dt>{{ t('timeTracking.totals.target') }}</dt>
        <dd>{{ formatDuration(totals.target_seconds) }}</dd>
      </div>
      <div class="tt-figure">
        <dt>{{ t('timeTracking.totals.monthBalance') }}</dt>
        <dd :class="signedClass(totals.balance_seconds)">
          {{ formatSignedDuration(totals.balance_seconds) }}
        </dd>
      </div>
    </dl>

    <p class="tt-muted tt-as-of" data-testid="time-tracking-as-of">
      {{ t('timeTracking.totals.dataAsOf', { time: formatISOTime(fetchedAt) }) }}
    </p>
  </SectionCard>
</template>

<style scoped lang="scss">
.tt-subtitle {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.tt-status {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.tt-muted {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.tt-figures {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(8.5rem, 1fr));
  gap: var(--space-2) var(--space-4);
  margin: 0;
}

.tt-figure {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);

  dt {
    font-size: var(--font-size-xs);
    color: var(--p-text-muted-color);
  }

  dd {
    margin: 0;
    font-size: var(--font-size-lg);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
}

.tt-figure--hero dd {
  font-size: var(--font-size-xl);
}

.is-negative {
  color: var(--p-red-500);
}

.tt-as-of {
  margin: 0;
  font-size: var(--font-size-xs);
}
</style>
