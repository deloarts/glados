<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import { HelpButton } from '@/shared/help'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import {
  PrintTemplateEditorDialog,
  PrintTemplateManagementControls,
  PrintTemplateManagementTable,
  PrintTemplatePreviewDialog,
  usePrintTemplatesStore,
} from '@/features/print-labels'

import type { PrintTemplateResponse } from '@/features/print-labels'

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
  idPrefix: 'print-dockets',
  showCreate: false,
  searchPlaceholder: t('printDockets.controls.search'),
}))
</script>

<template>
  <!-- ManagementCrudShell renders the ConfirmDialog the bulk actions use. -->
  <ManagementCrudShell :config="shellConfig" v-model:search="search">
    <template #handbook>
      <HelpButton rounded />
    </template>
    <template #extra-controls>
      <PrintTemplateManagementControls kind="docket" />
    </template>
    <PrintTemplateManagementTable kind="docket" @edit="openEdit" @preview="openPreview" />
  </ManagementCrudShell>

  <PrintTemplateEditorDialog
    v-model:visible="showEditorDialog"
    kind="docket"
    :template="editingTemplate"
  />
  <PrintTemplatePreviewDialog
    v-model:visible="showPreviewDialog"
    kind="docket"
    :template="previewTemplate"
  />
</template>
