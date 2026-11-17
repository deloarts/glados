import { createFilesStore } from '@/core/stores/createFilesStore'

import {
  getSourceItemFiles,
  getSourceItemFilesForItems,
  uploadSourceItemFile,
  deleteSourceItemFile,
} from '../api/sourceItemFilesApi'
import { SINGLETON_FILE_CATEGORIES } from '../types/sourceItemsResponse'
import type { SourceItemFile, SourceItemFileCategory } from '../types/sourceItemsResponse'

export const useSourceItemFilesStore = createFilesStore<SourceItemFile, SourceItemFileCategory>(
  'sourceItemFiles',
  {
    getForItems: getSourceItemFilesForItems,
    getForItem: getSourceItemFiles,
    upload: uploadSourceItemFile,
    remove: deleteSourceItemFile,
    itemIdOf: (file) => file.source_item_id,
    singletonCategories: SINGLETON_FILE_CATEGORIES,
  },
)
