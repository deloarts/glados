import { createDemandSelectionStore } from '@/shared/stores/createDemandSelectionStore'
import type { MadeItemDemandResponse } from '@/features/made-items'


export const useMadeItemsProcurementStore =
  createDemandSelectionStore<MadeItemDemandResponse>('madeItemsProcurement')
