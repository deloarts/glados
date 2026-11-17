import type { ArticleGroupResponse } from '@/features/article-groups'
import type { Schemas } from '@/core/api/generated'

export type { ArticleGroupResponse }

export type BoughtItemCatalogueStatus = Schemas['BoughtItemCatalogueStatus']

export type BoughtItemFileCategory = Schemas['BoughtItemFileCategory']

export const SINGLETON_FILE_CATEGORIES: BoughtItemFileCategory[] = [
  'step',
  'mesh',
]

export type BoughtItemFile = Schemas['BoughtItemFileResponse']

/** Slim PDF-file projection embedded in the catalogue list response. */
export type BoughtItemPdfFile = Schemas['BoughtItemPdfFileResponse']

export type BoughtItemResponse = Schemas['BoughtItemWebResponse']

export type BoughtItemMergeTargetResponse = Schemas['BoughtItemMergeTargetResponse']
