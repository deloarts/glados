<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import PanelLoading from './PanelLoading.vue'

import { MadeItemThumbnailCell, useMadeItemLabel } from '@/features/made-items'
import { BoughtItemThumbnailCell } from '@/features/bought-items'
import { formatISODate } from '@/core/utils/dates'
import type { RecentCatalogueItem } from '../composables/useDashboardSummary'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

defineProps<{
  items: RecentCatalogueItem[]
  loading: boolean
}>()

const { t } = useI18n()
const router = useRouter()
const { format: madeItemLabel } = useMadeItemLabel()

function openCatalogue(item: RecentCatalogueItem): void {
  void router.push(item.type === 'made' ? '/catalogue/made-items' : '/catalogue/bought-items')
}

function partNumberLabel(item: RecentCatalogueItem): string {
  if (item.type === 'made') return madeItemLabel(item.partNumber, item.revision)
  return item.partNumber ?? getEmptyPlaceholder()
}
</script>

<template>
  <div class="card recent-items-panel">
    <div class="panel-title">
      <i class="mdi mdi-new-box" aria-hidden="true" />
      <span>{{ t('dashboard.recentItems.title') }}</span>
    </div>

    <PanelLoading v-if="loading && items.length === 0" class="panel-loading" />

    <div v-else-if="items.length === 0" class="panel-empty">
      <span>{{ t('dashboard.recentItems.empty') }}</span>
    </div>

    <ul v-else class="recent-items-list">
      <li v-for="item in items" :key="`${item.type}-${item.itemId}`">
        <button type="button" class="recent-items-row" @click="openCatalogue(item)">
          <MadeItemThumbnailCell
            v-if="item.type === 'made'"
            :item-id="item.itemId"
            :item-name="item.label"
            size="2.25rem"
            no-image-icon="mdi mdi-cog-outline"
          />
          <BoughtItemThumbnailCell
            v-else
            :item-id="item.itemId"
            :item-name="item.label"
            size="2.25rem"
            no-image-icon="mdi mdi-cube-outline"
          />
          <div class="recent-items-info">
            <span class="recent-items-label">{{ item.label }}</span>
            <span class="recent-items-sub">{{ partNumberLabel(item) }} · {{ formatISODate(item.created) }}</span>
          </div>
          <Tag
            :severity="item.type === 'made' ? 'help' : 'info'"
            :value="
              t(
                item.type === 'made' ? 'dashboard.recentItems.made' : 'dashboard.recentItems.bought',
              )
            "
          />
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped lang="scss">
.recent-items-panel {
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
  align-items: center;
  justify-content: center;
  color: var(--p-text-muted-color);
  padding: var(--space-5) 0;
  flex: 1 1 auto;
}

.recent-items-list {
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

.recent-items-row {
  display: flex;
  align-items: center;
  width: 100%;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-2);
  border-radius: var(--p-content-border-radius);
  border: none;
  background: none;
  font: inherit;
  color: inherit;
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

.recent-items-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1 1 auto;
}

.recent-items-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-items-sub {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
