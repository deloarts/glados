import { createDemandSelectionStore } from '@/shared/stores/createDemandSelectionStore'
import type { SourceItemDemandResponse } from '@/features/source-items'


export const useSourceItemDemandsSelectionStore =
  createDemandSelectionStore<SourceItemDemandResponse>('sourceItemDemandsSelection')
