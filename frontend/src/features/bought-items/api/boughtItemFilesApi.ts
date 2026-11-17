/** Bought item file attachments, built from the shared files factory. */
import { createFilesApi } from '@/shared/api/createFilesApi'

import type { BoughtItemFile, BoughtItemFileCategory } from '../types/boughtItemsResponse'

const filesApi = createFilesApi<{ file: BoughtItemFile; category: BoughtItemFileCategory }>(
  'bought',
)

export const getBoughtItemFiles = filesApi.list
export const getBoughtItemFilesForItems = filesApi.listForItems
export const uploadBoughtItemFile = filesApi.upload
export const deleteBoughtItemFile = filesApi.remove
export const getBoughtItemFileBlob = filesApi.getBlob
