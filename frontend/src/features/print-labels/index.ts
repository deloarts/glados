// Public barrel of the print-labels feature. Other features import through
// here (enforced by eslint).

export { printDocuments } from './api/printDocuments'
export { printLotScrapTag } from './api/printLotScrapTag'
export { downloadPrintTemplate } from './api/downloadPrintTemplate'
export { usePrintTemplatesStore } from './stores/printTemplatesStore'

// Shared by the label and docket management pages, selected by a kind prop.
export { default as PrintTemplateManagementControls } from './components/PrintTemplateManagementControls.vue'
export { default as PrintTemplateManagementTable } from './components/PrintTemplateManagementTable.vue'
export { default as PrintTemplateEditorDialog } from './components/PrintTemplateEditorDialog.vue'
export { default as PrintTemplatePreviewDialog } from './components/PrintTemplatePreviewDialog.vue'

export type {
  PrintTemplateResponse,
  FieldSourceResponse,
} from './types/printTemplateResponse'

// The print provider the app shell installs, see @/shared/print.
export { templatePrinting } from './templatePrinting'
