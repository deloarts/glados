import { createFilesStore } from '@/core/stores/createFilesStore'

import {
  getMadeItemFiles,
  getMadeItemFilesForItems,
  uploadMadeItemFile,
  deleteMadeItemFile,
} from '../api/madeItemFilesApi'
import { SINGLETON_FILE_CATEGORIES } from '../types/madeItemsResponse'
import type { MadeItemFile, MadeItemFileCategory } from '../types/madeItemsResponse'

export const useMadeItemFilesStore = createFilesStore<MadeItemFile, MadeItemFileCategory>(
  'madeItemFiles',
  {
    getForItems: getMadeItemFilesForItems,
    getForItem: getMadeItemFiles,
    upload: uploadMadeItemFile,
    remove: deleteMadeItemFile,
    itemIdOf: (file) => file.made_item_id,
    singletonCategories: SINGLETON_FILE_CATEGORIES,
  },
)
