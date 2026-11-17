<script setup lang="ts">
// Observing step of the Auto-Plan dialog: progress of a run someone else
// started, polled from the run store while it lasts.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import { useAutoPlanRunStore } from '../stores/autoPlanRunStore'

const { t } = useI18n()
const runStore = useAutoPlanRunStore()

// Resolved once so the template's v-if narrows it to non-null.
const observerRun = computed(() => runStore.activeRun)

const observerPercent = computed<number | null>(() => {
  const run = observerRun.value
  if (!run || run.current === null || run.total === null || run.total === 0) return null
  return Math.min(100, Math.max(0, (run.current / run.total) * 100))
})

const observerStartedLine = computed(() => {
  const run = observerRun.value
  if (!run) return ''
  const startedBy = t('productionSchedule.autoPlan.observer.startedBy', { user: run.user_name })
  const startedAt = t('productionSchedule.autoPlan.observer.startedAt', {
    time: formatISODateTime(run.started_at),
  })
  return `${startedBy} ${startedAt}`
})
</script>

<template>
  <div class="autoplan-observing">
    <template v-if="observerRun">
      <p class="observer-title">{{ t('productionSchedule.autoPlan.observer.title') }}</p>
      <p class="observer-started">{{ observerStartedLine }}</p>

      <p class="stage-label" role="status" aria-live="polite">
        {{ observerRun.stage ? t('productionSchedule.autoPlan.progress.' + observerRun.stage) : '' }}
      </p>

      <ProgressBar v-if="observerPercent === null" mode="indeterminate" />
      <ProgressBar v-else :value="observerPercent" />

      <p
        v-if="observerRun.current !== null && observerRun.total !== null"
        class="counter-line"
        role="status"
        aria-live="polite"
      >
        {{
          t('productionSchedule.autoPlan.progress.counter', {
            current: observerRun.current,
            total: observerRun.total,
          })
        }}
      </p>

      <p class="observer-blocked">{{ t('productionSchedule.autoPlan.observer.blocked') }}</p>
    </template>
  </div>
</template>

<style scoped lang="scss">
.autoplan-observing {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.stage-label {
  font-weight: 500;
}

.counter-line {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.observer-title {
  font-weight: 600;
}

.observer-started,
.observer-blocked {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
