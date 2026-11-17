<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import PanelLoading from './PanelLoading.vue'

import ProgressMeter from './ProgressMeter.vue'
import { MadeItemThumbnailCell, useMadeItemLabel } from '@/features/made-items'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import type { WipLotResponse } from '@/features/production'

const props = defineProps<{
  wipLots: WipLotResponse[]
  loading: boolean
}>()

const { t } = useI18n()
const { openLotDetail } = useLotDetail()
const { format: madeItemLabel } = useMadeItemLabel()

const MAX_ROWS = 8

// Least-complete lots surface first, they need the most attention.
const rows = computed(() =>
  [...props.wipLots]
    .sort((a, b) => {
      const ratioA = a.raw_count > 0 ? a.finished_count / a.raw_count : 0
      const ratioB = b.raw_count > 0 ? b.finished_count / b.raw_count : 0
      return ratioA - ratioB
    })
    .slice(0, MAX_ROWS),
)

function openLot(lot: WipLotResponse): void {
  openLotDetail(lot.id)
}
</script>

<template>
  <div class="card wip-progress-panel">
    <div class="panel-title">
      <i class="mdi mdi-progress-wrench" aria-hidden="true" />
      <span>{{ t('dashboard.wip.title') }}</span>
    </div>

    <PanelLoading v-if="loading && rows.length === 0" class="panel-loading" />

    <div v-else-if="rows.length === 0" class="panel-empty">
      <i class="mdi mdi-check-circle-outline panel-empty-icon" aria-hidden="true" />
      <span>{{ t('dashboard.wip.empty') }}</span>
    </div>

    <div v-else class="wip-list">
      <div
        v-for="lot in rows"
        :key="lot.id"
        class="wip-row"
        role="button"
        tabindex="0"
        @click="openLot(lot)"
        @keydown.enter="openLot(lot)"
        @keydown.space.prevent="openLot(lot)"
      >
        <MadeItemThumbnailCell
          :item-id="lot.made_item_id"
          :item-name="lot.made_item_article_name"
          size="2rem"
          no-image-icon="mdi mdi-cog-outline"
        />
        <ProgressMeter
          class="wip-row-meter"
          :label="`${lot.lot_number} · ${madeItemLabel(lot.made_item_part_number, lot.made_item_revision)}`"
          :value="lot.finished_count"
          :max="lot.raw_count"
        />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.wip-progress-panel {
  gap: var(--space-3);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
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
  color: var(--p-green-500);
}

.wip-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

.wip-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--p-content-border-radius);
  transition: background-color 0.15s;

  &:hover {
    background-color: var(--p-content-hover-background);
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: -2px;
  }
}

.wip-row-meter {
  flex: 1 1 auto;
  min-width: 0;
}
</style>
