import type { Schemas } from '@/core/api/generated'

export type SourceItemCatalogueStatus = Schemas['SourceItemCatalogueStatus']

// Raw stock has no STEP, drawing or DXF slot.
export type SourceItemFileCategory = Schemas['SourceItemFileCategory']

export const SINGLETON_FILE_CATEGORIES: SourceItemFileCategory[] = ['mesh']

export type SourceItemFile = Schemas['SourceItemFileResponse']

export type SourceItemResponse = Schemas['SourceItemWebResponse']
