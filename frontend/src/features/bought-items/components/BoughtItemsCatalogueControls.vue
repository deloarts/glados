<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

import BoughtItemCreateForm from './BoughtItemCreateForm.vue'
import BoughtItemsImportDialog from './BoughtItemsImportDialog.vue'
import { useBoughtItemsImportDraftStore } from '../stores/boughtItemsImportDraftStore'
import { useBoughtItemsStore } from '../stores/boughtItemsStore'
import { useBoughtItemsCatalogueEditStore } from '../stores/boughtItemsCatalogueEditStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import CatalogueControlsBar from '@/shared/components/resource-view/CatalogueControlsBar.vue'
import { HelpButton } from '@/shared/help'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { usePdmPreviewStore } from '@/shared/pdm-preview/pdmPreviewStore'
import { SpreadsheetExportButton } from '@/shared/spreadsheet-export'
import { useBoughtItemsCatalogueExport } from '../composables/useBoughtItemsCatalogueExport'

const showCreateForm = ref(false)
const showImport = ref(false)
const importDraftStore = useBoughtItemsImportDraftStore()

const { t } = useI18n()
const boughtItemsStore = useBoughtItemsStore()
const editStore = useBoughtItemsCatalogueEditStore()
const { hasPermission } = usePermissions()
const hostStore = useHostStore()
const pdmPreviewStore = usePdmPreviewStore()

const canWrite = computed(() => hasPermission(Permission.WRITE_BOUGHT_ITEMS))
const { missing } = useMissingPermission()
// A missing permission names itself; otherwise a kept draft is the hint.
const importHint = computed(
  () =>
    missing(Permission.WRITE_BOUGHT_ITEMS) ||
    (importDraftStore.hasDraft ? t('boughtItems.import.draftIndicator') : ''),
)
// See MadeItemsCatalogueControls.vue's canCreate for the full reasoning.

const canCreate = computed(() => hostStore.boughtItemPartNumbers.web_creation_allowed)

const spreadsheetExport = useBoughtItemsCatalogueExport()
const { exporting, loaded: exportLoaded, total: exportTotal } = spreadsheetExport

const pdmPreviewEnabled = computed(() => pdmPreviewStore.state.bought.enabled)
const pdmPreviewCount = computed(() => pdmPreviewStore.state.bought.unlinked.length)

const emit = defineEmits<{
  'toggle-pdm-preview': []
}>()

function onItemCreated(): void {
  void boughtItemsStore.refresh()
}
</script>

<template>
  <CatalogueControlsBar
    i18n-prefix="boughtItems.catalogue.controls"
    :can-write="canWrite"
    :write-blocked="missing(Permission.WRITE_BOUGHT_ITEMS)"
    :edit-mode="editStore.editMode"
    :show-create="canCreate"
    @create="showCreateForm = true"
    @toggle-edit="editStore.toggleEditMode()"
  >
    <template #after-create>
      <span v-if="canCreate" v-tooltip="importHint || undefined">
        <Button
          :label="t('boughtItems.catalogue.controls.importFile')"
          icon="mdi mdi-file-excel-outline"
          severity="contrast"
          text
          :disabled="!canWrite"
          :badge="importDraftStore.hasDraft ? ' ' : undefined"
          badge-severity="warn"
          data-testid="bought-items-import-open"
          @click="showImport = true"
        />
      </span>
    </template>
    <template #after-edit>
      <SpreadsheetExportButton
        :total="boughtItemsStore.total"
        :selected-count="editStore.selectedItems.length"
        :exporting="exporting"
        :loaded="exportLoaded"
        :export-total="exportTotal"
        @export="(scope) => void spreadsheetExport.run(scope)"
        @cancel="spreadsheetExport.cancel()"
      />
    </template>
    <template #handbook>
      <Button
        v-if="pdmPreviewEnabled"
        :label="t('pdmPreview.controls.toggle', { count: pdmPreviewCount })"
        icon="mdi mdi-file-cad-box"
        severity="contrast"
        text
        @click="emit('toggle-pdm-preview')"
      />
      <HelpButton slug="catalogue/bought-items" rounded />
    </template>
  </CatalogueControlsBar>

  <BoughtItemCreateForm v-model:visible="showCreateForm" @created="onItemCreated" />
  <BoughtItemsImportDialog v-if="showImport" v-model:visible="showImport" @created="onItemCreated" />
</template>
