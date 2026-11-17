/** Made item file attachments, built from the shared files factory. */
import { createFilesApi } from '@/shared/api/createFilesApi'

import type { MadeItemFile, MadeItemFileCategory } from '../types/madeItemsResponse'

const filesApi = createFilesApi<{ file: MadeItemFile; category: MadeItemFileCategory }>('made')

export const getMadeItemFiles = filesApi.list
export const getMadeItemFilesForItems = filesApi.listForItems
export const uploadMadeItemFile = filesApi.upload
export const deleteMadeItemFile = filesApi.remove
export const getMadeItemFileBlob = filesApi.getBlob
