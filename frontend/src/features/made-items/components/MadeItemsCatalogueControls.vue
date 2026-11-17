<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

import MadeItemCreateForm from './MadeItemCreateForm.vue'
import { useMadeItemsStore } from '../stores/madeItemsStore'
import { useMadeItemsCatalogueEditStore } from '../stores/madeItemsCatalogueEditStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import CatalogueControlsBar from '@/shared/components/resource-view/CatalogueControlsBar.vue'
import { HelpButton } from '@/shared/help'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { usePdmPreviewStore } from '@/shared/pdm-preview/pdmPreviewStore'
import { SpreadsheetExportButton } from '@/shared/spreadsheet-export'
import { useMadeItemsCatalogueExport } from '../composables/useMadeItemsCatalogueExport'

const showCreateForm = ref(false)

const { t } = useI18n()
const madeItemsStore = useMadeItemsStore()
const editStore = useMadeItemsCatalogueEditStore()
const { hasPermission } = usePermissions()
const hostStore = useHostStore()
const pdmPreviewStore = usePdmPreviewStore()

const canWrite = computed(() => hasPermission(Permission.WRITE_MADE_ITEMS))
const { missing } = useMissingPermission()
// Hides the entry point entirely once the resolved policy says web
// creation of made items is off (only actually false once PDM is enabled
// and the admin setting agrees). Context-menu "New revision"/"Copy" are a
// separate change, unaffected by this flag.
const canCreate = computed(() => hostStore.madeItemPartNumbers.web_creation_allowed)

const spreadsheetExport = useMadeItemsCatalogueExport()
const { exporting, loaded: exportLoaded, total: exportTotal } = spreadsheetExport

const pdmPreviewEnabled = computed(() => pdmPreviewStore.state.made.enabled)
const pdmPreviewCount = computed(() => pdmPreviewStore.state.made.unlinked.length)

const emit = defineEmits<{
  'toggle-pdm-preview': []
}>()

function onItemCreated(): void {
  void madeItemsStore.refresh()
}
</script>

<template>
  <CatalogueControlsBar
    i18n-prefix="madeItems.catalogue.controls"
    :can-write="canWrite"
    :write-blocked="missing(Permission.WRITE_MADE_ITEMS)"
    :edit-mode="editStore.editMode"
    :show-create="canCreate"
    @create="showCreateForm = true"
    @toggle-edit="editStore.toggleEditMode()"
  >
    <template #after-edit>
      <SpreadsheetExportButton
        :total="madeItemsStore.total"
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
      <HelpButton slug="catalogue/made-items" rounded />
    </template>
  </CatalogueControlsBar>

  <MadeItemCreateForm v-model:visible="showCreateForm" @created="onItemCreated" />
</template>
