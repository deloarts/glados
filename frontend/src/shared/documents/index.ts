// Public surface of the document control pieces every controlled document
// page shares, whatever its document type: the lifecycle with its
// permissions and actions, the edit lock, the notices of a lock and of an
// invalid revision, the reason dialog, the local copy of unsaved changes,
// the row links and menu and the revision label. The rules
// themselves live in the backend.
export { default as DocumentInvalidNotice } from './components/DocumentInvalidNotice.vue'
export { default as DocumentLockNotice } from './components/DocumentLockNotice.vue'
export { default as DocumentDraftDialog } from './components/DocumentDraftDialog.vue'
export { default as DocumentReasonDialog } from './components/DocumentReasonDialog.vue'
export { useControlledDocument } from './composables/useControlledDocument'
export { LOCK_IDLE_MS, LOCK_RENEW_MS, useDocumentLock } from './composables/useDocumentLock'
export { DOCUMENT_PAGE_ACTIONS, useDocumentPageAction } from './composables/useDocumentPageAction'
export { useDocumentRowLinks } from './composables/useDocumentRowLinks'
export { LOCAL_DRAFT_WRITE_MS, useLocalDraft } from './composables/useLocalDraft'
export { readLocalDraft, removeLocalDraft, writeLocalDraft } from './utils/localDraft'
export { documentReportNotice } from './utils/reportNotice'
export { editingBy } from './utils/lock'
export { documentRowMenu, documentRowStep, documentRowSteps } from './utils/rowMenu'
export { documentReference, revisionLabel } from './utils/revision'

export type {
  ControlledDocumentApi,
  ControlledDocumentOptions,
  DocumentAction,
  DocumentPermissions,
  LifecycleDocument,
  OfferedContext,
} from './composables/useControlledDocument'
export type { DocumentLock, DocumentLockOptions } from './composables/useDocumentLock'
export type { LocalDraftHandle, LocalDraftOffer, LocalDraftOptions } from './composables/useLocalDraft'
export type { DocumentPageAction } from './composables/useDocumentPageAction'
export type { LocalDraft } from './utils/localDraft'
export type {
  DocumentRowMenuOptions,
  DocumentRowPermissions,
  DocumentRowReasons,
  DocumentRowStep,
} from './utils/rowMenu'
export type { DocumentReportNotice } from './utils/reportNotice'
export type { ControlledDocument } from './types'
