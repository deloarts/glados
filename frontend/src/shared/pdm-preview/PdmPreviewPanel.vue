<script setup lang="ts">
// Catalogue-facing PDM preview panel: files the vault has that this kind's
// catalogue has never ingested, so a user can see what's coming without
// opening PDM. Read-only: no selection, no row click, nothing here creates
// or changes an item. Rows are visually muted (`.pdm-preview-row`) to
// reinforce that this is a PDM-side listing, not a catalogue row.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { formatDateTimeOrDash } from '@/core/utils/dates'
import { usePdmPreviewStore } from './pdmPreviewStore'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { PdmItemKind, PdmPreviewFileResponse } from './api'

const props = defineProps<{
  kind: PdmItemKind
}>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const store = usePdmPreviewStore()

const rows = computed(() => store.state[props.kind].unlinked)
const loading = computed(() => (props.kind === 'made' ? store.loadingMade : store.loadingBought))
</script>

<template>
  <DataTable
    class="pdm-preview-table"
    :value="rows"
    data-key="file_id"
    size="small"
    scrollable
    scroll-height="320px"
    :loading="loading"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    :row-class="() => 'pdm-preview-row'"
  >
    <template #empty>
      <EmptyState :message="t('pdmPreview.panel.empty')" />
    </template>

    <Column style="width: 2.75rem">
      <template #body>
        <i
          class="mdi mdi-file-cad-box pdm-only-icon"
          aria-hidden="true"
          v-tooltip.top="t('pdmPreview.panel.pdmOnly')"
        />
      </template>
    </Column>

    <Column :header="t('pdmPreview.panel.columns.partNumber')" style="width: 10rem">
      <template #body="{ data }: { data: PdmPreviewFileResponse }">{{ data.part_number }}</template>
    </Column>

    <Column :header="t('pdmPreview.panel.columns.revision')" style="width: 6rem">
      <template #body="{ data }: { data: PdmPreviewFileResponse }">
        {{ data.revision ?? getEmptyPlaceholder() }}
      </template>
    </Column>

    <Column :header="t('pdmPreview.panel.columns.articleName')" style="width: 14rem">
      <template #body="{ data }: { data: PdmPreviewFileResponse }">
        {{ data.article_name ?? getEmptyPlaceholder() }}
      </template>
    </Column>

    <Column :header="t('pdmPreview.panel.columns.file')" style="width: 14rem">
      <template #body="{ data }: { data: PdmPreviewFileResponse }">
        <div class="file-cell">
          <span class="file-name">{{ data.name }}</span>
          <span class="file-path" v-tooltip.top="data.path">{{ data.path }}</span>
        </div>
      </template>
    </Column>

    <Column
      field="version"
      :header="t('pdmPreview.panel.columns.version')"
      style="width: 6rem"
    />

    <Column :header="t('pdmPreview.panel.columns.state')" style="width: 9rem">
      <template #body="{ data }: { data: PdmPreviewFileResponse }">{{ data.state }}</template>
    </Column>

    <Column :header="t('pdmPreview.panel.columns.modifiedAt')" style="width: 11rem">
      <template #body="{ data }: { data: PdmPreviewFileResponse }">
        {{ formatDateTimeOrDash(data.modified_at) }}
      </template>
    </Column>

    <Column :header="t('pdmPreview.panel.columns.syncState')">
      <template #body="{ data }: { data: PdmPreviewFileResponse }">
        <span
          v-if="data.last_error"
          v-tooltip.top="data.last_error"
          class="sync-error"
        >
          {{ t(`pdmPreview.panel.syncStates.${data.sync_state}`) }}
        </span>
        <span v-else>{{ t(`pdmPreview.panel.syncStates.${data.sync_state}`) }}</span>
      </template>
    </Column>
  </DataTable>
</template>

<style scoped lang="scss">
.pdm-preview-table {
  width: 100%;
  // Bounded, not scrollHeight="flex": this panel sits above the main
  // catalogue table inside the same flex column and must not compete with
  // it for the whole remaining height. See MadeItemCatalogueView.vue's and
  // BoughtItemCatalogueView.vue's own `flex: 1 1 auto` fix on the table
  // below it.
  flex: 0 0 auto;
}

:deep(.pdm-preview-row) {
  color: var(--p-text-muted-color);
}

.pdm-only-icon {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-lg);
}

.file-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.file-name {
  font-size: var(--font-size-sm);
}

.file-path {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sync-error {
  text-decoration: underline dotted;
  cursor: help;
}
</style>
