import { createDemandImportDraftStore } from '@/shared/demand-import'
import { madeItemsDemandImportAdapter } from '../utils/madeItemsDemandImportAdapter'

// The made-items instantiation of the generic demand-import draft store
// (src/shared/demand-import/stores/createDemandImportDraftStore.ts). Mirrors
// boughtItemsDemandsBatchDraftStore.ts.
export const useMadeItemsDemandsBatchDraftStore = createDemandImportDraftStore(
  madeItemsDemandImportAdapter,
)
