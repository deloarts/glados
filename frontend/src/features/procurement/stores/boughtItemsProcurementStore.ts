import { createDemandSelectionStore } from '@/shared/stores/createDemandSelectionStore'
import type { BoughtItemDemandResponse } from '@/features/bought-items'


export const useBoughtItemsProcurementStore =
  createDemandSelectionStore<BoughtItemDemandResponse>('boughtItemsProcurement')
