/** Source item file attachments, built from the shared files factory. */
import { createFilesApi } from '@/shared/api/createFilesApi'

import type { SourceItemFile, SourceItemFileCategory } from '../types/sourceItemsResponse'

const filesApi = createFilesApi<{ file: SourceItemFile; category: SourceItemFileCategory }>(
  'source',
)

export const getSourceItemFiles = filesApi.list
export const getSourceItemFilesForItems = filesApi.listForItems
export const uploadSourceItemFile = filesApi.upload
export const deleteSourceItemFile = filesApi.remove
export const getSourceItemFileBlob = filesApi.getBlob
