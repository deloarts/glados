<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import { HelpButton } from '@/shared/help'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import PrintTemplateManagementControls from '../components/PrintTemplateManagementControls.vue'
import PrintTemplateManagementTable from '../components/PrintTemplateManagementTable.vue'
import PrintTemplateEditorDialog from '../components/PrintTemplateEditorDialog.vue'
import PrintTemplatePreviewDialog from '../components/PrintTemplatePreviewDialog.vue'
import { usePrintTemplatesStore } from '../stores/printTemplatesStore'

import type { PrintTemplateResponse } from '../types/printTemplateResponse'

const { t } = useI18n()
const store = usePrintTemplatesStore()
const { search } = storeToRefs(store)

const showEditorDialog = ref(false)
const editingTemplate = ref<PrintTemplateResponse | null>(null)
const showPreviewDialog = ref(false)
const previewTemplate = ref<PrintTemplateResponse | null>(null)

function openEdit(template: PrintTemplateResponse): void {
  editingTemplate.value = template
  showEditorDialog.value = true
}

function openPreview(template: PrintTemplateResponse): void {
  previewTemplate.value = template
  showPreviewDialog.value = true
}

// Rows are seeded and never created, so the shell's Create button is hidden
// and the bulk actions take its place.
const shellConfig = computed<ManagementCrudShellConfig>(() => ({
  store,
  idPrefix: 'print-labels',
  showCreate: false,
  searchPlaceholder: t('printLabels.controls.search'),
}))
</script>

<template>
  <!-- ManagementCrudShell renders the ConfirmDialog the bulk actions use. -->
  <ManagementCrudShell :config="shellConfig" v-model:search="search">
    <template #handbook>
      <HelpButton rounded />
    </template>
    <template #extra-controls>
      <PrintTemplateManagementControls kind="label" />
    </template>
    <PrintTemplateManagementTable kind="label" @edit="openEdit" @preview="openPreview" />
  </ManagementCrudShell>

  <PrintTemplateEditorDialog
    v-model:visible="showEditorDialog"
    kind="label"
    :template="editingTemplate"
  />
  <PrintTemplatePreviewDialog
    v-model:visible="showPreviewDialog"
    kind="label"
    :template="previewTemplate"
  />
</template>
