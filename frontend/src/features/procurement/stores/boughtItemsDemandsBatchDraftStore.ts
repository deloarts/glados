import { createDemandImportDraftStore } from '@/shared/demand-import'
import { boughtItemsDemandImportAdapter } from '../utils/boughtItemsDemandImportAdapter'

// The bought items instance of the generic demand import draft store.
export const useBoughtItemsDemandsBatchDraftStore = createDemandImportDraftStore(
  boughtItemsDemandImportAdapter,
)
