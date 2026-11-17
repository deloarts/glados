<script setup lang="ts">
// Running step of the Auto-Plan dialog: the current stage, progress and a
// live feed of placed and skipped orders streamed by this user's run.
import { nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAutoPlanRunStore } from '../stores/autoPlanRunStore'
import { useAutoPlanTargetLabels } from '../composables/useAutoPlanTargetLabels'
import { skipReasonLabelKey, skipReasonTooltipKey } from '../utils/autoPlanSkipReasons'

const props = defineProps<{
  machineNameById: Record<number, string>
  poolNameById: Record<number, string>
}>()

const { t } = useI18n()
const runStore = useAutoPlanRunStore()
const { machineLabel, poolLabel } = useAutoPlanTargetLabels(
  () => props.machineNameById,
  () => props.poolNameById,
)

function afterIsPool(order: {
  after_machine_id: number | null
  after_machine_pool_id: number | null
}): boolean {
  return order.after_machine_id === null && order.after_machine_pool_id !== null
}

// The feed scrolls to the newest row as it streams in.
const feedListRef = ref<HTMLElement | null>(null)
watch(
  () => runStore.feed.length,
  async () => {
    await nextTick()
    if (feedListRef.value) {
      feedListRef.value.scrollTop = feedListRef.value.scrollHeight
    }
  },
)
</script>

<template>
  <div class="autoplan-running">
    <p class="stage-label" role="status" aria-live="polite">
      {{ runStore.stage ? t('productionSchedule.autoPlan.progress.' + runStore.stage) : '' }}
    </p>

    <ProgressBar v-if="runStore.percent === null" mode="indeterminate" />
    <ProgressBar v-else :value="runStore.percent" />

    <p
      v-if="runStore.current !== null && runStore.total !== null"
      class="counter-line"
      role="status"
      aria-live="polite"
    >
      {{
        t('productionSchedule.autoPlan.progress.counter', {
          current: runStore.current,
          total: runStore.total,
        })
      }}
    </p>

    <p class="background-hint">{{ t('productionSchedule.autoPlan.progress.backgroundHint') }}</p>

    <div ref="feedListRef" class="autoplan-feed">
      <div
        v-for="entry in runStore.feed"
        :key="entry.order_id"
        class="feed-row"
        :class="{ 'feed-row-skipped': !entry.placed }"
      >
        <span class="feed-order">{{ entry.production_order_number }}</span>
        <span class="feed-move">
          <span>{{ machineLabel(entry.before_machine_id) }}</span>
          <i class="mdi mdi-arrow-right" aria-hidden="true" />
          <Tag
            v-if="afterIsPool(entry)"
            :value="t('productionQueue.card.poolTag', { pool: poolLabel(entry.after_machine_pool_id!) })"
            severity="info"
            icon="mdi mdi-view-grid-outline"
          />
          <span v-else>{{ machineLabel(entry.after_machine_id) }}</span>
        </span>
        <!-- A skip with a reason names it as the result does; the manual-step
             skip has none and keeps the plain tag. -->
        <Tag
          v-if="!entry.placed && entry.reason"
          v-tooltip.top="t(skipReasonTooltipKey(entry.reason))"
          class="feed-skip-reason"
          :value="t(skipReasonLabelKey(entry.reason))"
          severity="secondary"
        />
        <Tag
          v-else-if="!entry.placed"
          :value="t('productionSchedule.autoPlan.progress.skippedTag')"
          severity="secondary"
        />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.autoplan-running {
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

.background-hint {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.autoplan-feed {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-height: 14rem;
  overflow-y: auto;
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.feed-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}

.feed-row-skipped {
  color: var(--p-text-muted-color);
}

.feed-order {
  flex: 0 0 auto;
  font-weight: 500;
}

.feed-move {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  gap: var(--space-1);
  min-width: 0;
}
</style>
