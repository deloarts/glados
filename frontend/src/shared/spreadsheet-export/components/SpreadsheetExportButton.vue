<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'

import type { MenuItem } from 'openvue/menuitem'
import type { SpreadsheetExportScope } from '../types/spreadsheetExport'

// The Export button of a controls bar. A click exports every row of the
// current filter, and its menu offers the same or only the checked rows. A
// table without row selection passes no selectedCount and gets a plain
// button without the menu.
// While a filtered export reads its pages, the button shows the progress
// and a Cancel button stands beside it.
const props = defineProps<{
  /** The row count of the current filter. */
  total: number
  selectedCount?: number
  exporting: boolean
  loaded: number
  /** The row count the running export reads. */
  exportTotal: number
}>()

const emit = defineEmits<{
  export: [scope: SpreadsheetExportScope]
  cancel: []
}>()

const { t } = useI18n()
const { formatNumber: n } = useLocaleFormat()

const menuItems = computed<MenuItem[]>(() => [
  {
    label: t('spreadsheetExport.scope.filtered', { count: n(props.total) }),
    icon: 'mdi mdi-filter-outline',
    disabled: props.total === 0,
    command: () => emit('export', 'filtered'),
  },
  {
    label: t('spreadsheetExport.scope.selected', { count: n(props.selectedCount ?? 0) }),
    icon: 'mdi mdi-checkbox-marked-outline',
    disabled: !props.selectedCount,
    command: () => emit('export', 'selected'),
  },
])

const progressLabel = computed(() =>
  t('spreadsheetExport.progress', { loaded: n(props.loaded), total: n(props.exportTotal) }),
)
</script>

<template>
  <template v-if="exporting">
    <Button
      :label="progressLabel"
      severity="contrast"
      text
      loading
      data-testid="spreadsheet-export-progress"
    />
    <Button
      :label="t('common.cancel')"
      icon="mdi mdi-close"
      severity="contrast"
      text
      data-testid="spreadsheet-export-cancel"
      @click="emit('cancel')"
    />
  </template>
  <SplitButton
    v-else-if="selectedCount !== undefined"
    :label="t('spreadsheetExport.export')"
    icon="mdi mdi-file-excel-outline"
    severity="contrast"
    text
    :disabled="total === 0"
    :model="menuItems"
    :pt="{
      pcButton: { root: { 'data-testid': 'spreadsheet-export' } },
      pcDropdown: { root: { 'data-testid': 'spreadsheet-export-menu' } },
    }"
    @click="emit('export', 'filtered')"
  />
  <Button
    v-else
    :label="t('spreadsheetExport.export')"
    icon="mdi mdi-file-excel-outline"
    severity="contrast"
    text
    :disabled="total === 0"
    data-testid="spreadsheet-export"
    @click="emit('export', 'filtered')"
  />
</template>
