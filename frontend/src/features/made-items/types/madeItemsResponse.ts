import type { ArticleGroupResponse } from '@/features/article-groups'
import type { Schemas } from '@/core/api/generated'
import type { LocalizedText } from '@/shared/utils/localizedText'

export type { ArticleGroupResponse }

export type MadeItemCatalogueStatus = Schemas['MadeItemCatalogueStatus']

export type MadeItemFileCategory = Schemas['MadeItemFileCategory']

export const SINGLETON_FILE_CATEGORIES: MadeItemFileCategory[] = [
  'step',
  'mesh',
  'drawing',
  'dxf',
]

export type MadeItemFile = Schemas['MadeItemFileResponse']

// A process has either a fabrication method or an inspection method.
export type StepRole = Schemas['StepRole']

/**
 * Refines the generated loose fields into the union the backend's check
 * constraints guarantee.
 */
type MadeItemProcessCommon = Omit<
  Schemas['MadeItemProcessWebResponse'],
  'role' | 'fabrication_method_id' | 'inspection_method_id' | 'inspection_method_name'
>

export interface FabricationMadeItemProcess extends MadeItemProcessCommon {
  role: 'fabrication'
  fabrication_method_id: number
  inspection_method_id: null
  inspection_method_name: null
}

export interface InspectionMadeItemProcess extends MadeItemProcessCommon {
  role: 'inspection'
  fabrication_method_id: null
  inspection_method_id: number
  inspection_method_name: LocalizedText
}

export type MadeItemProcessResponse = FabricationMadeItemProcess | InspectionMadeItemProcess

/** changed_by is null while the item was never changed. */
export type MadeItemResponse = Omit<Schemas['MadeItemWebResponse'], 'processes'> & {
  processes: MadeItemProcessResponse[]
}

/** item carries the process role union like MadeItemResponse. */
export type MadeItemMergeTargetResponse = Omit<Schemas['MadeItemMergeTargetResponse'], 'item'> & {
  item: MadeItemResponse
}

/** A sibling with the same part number, newest first. */
export type MadeItemRevisionSummary = Schemas['MadeItemRevisionSummaryResponse']

/** reason explains a false can_create when the backend distinguishes it. */
export type MadeItemRevisionsResponse = Schemas['MadeItemRevisionsResponse']
