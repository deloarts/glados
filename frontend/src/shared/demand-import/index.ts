// Public surface of the generic demand-import module. An adapter (e.g.
// bought-items, made-items) plugs into createDemandImportDraftStore() and
// the three components below to get the whole upload -> map columns ->
// review -> validate -> commit flow. Parsing, header detection and column
// mapping come from shared/spreadsheet-import.
export { createDemandImportDraftStore } from './stores/createDemandImportDraftStore'

export { default as DemandImportDialog } from './components/DemandImportDialog.vue'
export { default as DemandImportReviewTable } from './components/DemandImportReviewTable.vue'
export { default as DemandImportRowFormDialog } from './components/DemandImportRowFormDialog.vue'

export type { DemandImportDraftStore } from './stores/createDemandImportDraftStore'
export type {
  DemandImportAdapter,
  DemandImportFieldSpec,
  DemandImportRow,
  DraftRow,
  ImportCommitResponse,
  ImportDivergence,
  ImportRowStatus,
  ImportRowValidation,
  ImportStep,
  ImportValidateResponse,
  ReviewColumnSpec,
} from './types/demandImport'
