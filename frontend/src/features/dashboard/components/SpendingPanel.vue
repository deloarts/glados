<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import PanelLoading from './PanelLoading.vue'

import SpendLineChart from './SpendLineChart.vue'
import { useCountUp } from '../composables/useCountUp'
import { useOrderFormatters } from '@/features/orders'

const props = defineProps<{
  spentRecentlyCents: number
  ordersCount: number
  dailySpendSeries: { day: number; cumulative: number; date: Date }[]
  loading: boolean
}>()

const { t } = useI18n()
const router = useRouter()
// Reuses the orders feature's own price formatter, so currency renders here
// exactly as it does in the orders table.
const { formatPrice } = useOrderFormatters()

// Counts up in cents; formatted only at render.
const spentDisplay = useCountUp(computed(() => Math.round(props.spentRecentlyCents)))
</script>

<template>
  <div
    class="card spending-panel"
    role="button"
    tabindex="0"
    @click="router.push('/procurement/orders')"
    @keydown.enter="router.push('/procurement/orders')"
    @keydown.space.prevent="router.push('/procurement/orders')"
  >
    <div class="panel-title">
      <i class="mdi mdi-chart-line" aria-hidden="true" />
      <span>{{ t('dashboard.spending.title') }}</span>
    </div>

    <PanelLoading v-if="loading && dailySpendSeries.length === 0" class="panel-loading" />

    <template v-else>
      <div class="spending-figures">
        <div class="spending-figure">
          <span class="spending-figure-value">{{ formatPrice(spentDisplay) }}</span>
          <span class="spending-figure-label">{{ t('dashboard.spending.spent') }}</span>
        </div>
        <div class="spending-figure">
          <span class="spending-figure-value">{{ ordersCount }}</span>
          <span class="spending-figure-label">{{ t('dashboard.spending.orders') }}</span>
        </div>
      </div>

      <SpendLineChart
        v-if="ordersCount > 0"
        :points="dailySpendSeries"
        :format-value="formatPrice"
      />
      <div v-else class="spending-empty">{{ t('dashboard.spending.empty') }}</div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.spending-panel {
  gap: var(--space-3);
  cursor: pointer;

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: -2px;
  }
}

.panel-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.panel-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5) 0;
  flex: 1 1 auto;
}

.spending-figures {
  display: flex;
  gap: var(--space-6);
}

.spending-figure {
  display: flex;
  flex-direction: column;
}

.spending-figure-value {
  font-size: var(--font-size-2xl);
  font-weight: 600;
  font-family: var(--font-head);
  line-height: 1.1;
}

.spending-figure-label {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.spending-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1 1 auto;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}
</style>
