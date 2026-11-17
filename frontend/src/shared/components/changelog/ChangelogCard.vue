<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { ChangelogEntry } from '@/shared/utils/changelog'

// Shared by all three kinds, whose changelog entries have the same shape.
defineProps<{
  entries: ChangelogEntry[]
  loading: boolean
  error: boolean
}>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
</script>

<template>
  <Panel :header="t('catalogue.itemDetail.cards.changelog')">
    <div class="card-scroll-body">
      <div v-if="loading && entries.length === 0" class="loading-state">
        <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
      </div>
      <div v-else-if="error" class="error-state">
        <i class="mdi mdi-alert-outline" aria-hidden="true" />
        {{ t('catalogue.itemDetail.sectionError') }}
      </div>
      <DataTable
        v-else
        :value="entries"
        size="small"
        :show-gridlines="isTableGridlinesEnabled"
        :striped-rows="isTableStripedEnabled"
      >
        <template #empty>
          <EmptyState :message="t('catalogue.itemDetail.changelog.empty')" />
        </template>
        <Column
          field="timestamp"
          :header="t('catalogue.itemDetail.changelog.columns.timestamp')"
          style="min-width: 11rem; white-space: nowrap"
        />
        <Column
          field="username"
          :header="t('catalogue.itemDetail.changelog.columns.user')"
          style="min-width: 8rem"
        />
        <Column
          field="message"
          :header="t('catalogue.itemDetail.changelog.columns.message')"
          style="width: 100%"
        />
      </DataTable>
    </div>
  </Panel>
</template>

<style scoped lang="scss">
.loading-state {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
  font-size: var(--font-size-2xl);
  color: var(--p-text-muted-color);
}

.error-state {
  padding: var(--space-5) 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
