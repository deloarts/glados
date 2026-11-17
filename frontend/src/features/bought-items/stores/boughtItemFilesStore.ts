import { LiveResource } from '@/core/realtime/resources'
import { createFilesStore } from '@/core/stores/createFilesStore'

import {
  getBoughtItemFiles,
  getBoughtItemFilesForItems,
  uploadBoughtItemFile,
  deleteBoughtItemFile,
} from '../api/boughtItemFilesApi'
import { SINGLETON_FILE_CATEGORIES } from '../types/boughtItemsResponse'
import type { BoughtItemFile, BoughtItemFileCategory } from '../types/boughtItemsResponse'

export const useBoughtItemFilesStore = createFilesStore<BoughtItemFile, BoughtItemFileCategory>(
  'boughtItemFiles',
  {
    getForItems: getBoughtItemFilesForItems,
    getForItem: getBoughtItemFiles,
    upload: uploadBoughtItemFile,
    remove: deleteBoughtItemFile,
    itemIdOf: (file) => file.bought_item_id,
    singletonCategories: SINGLETON_FILE_CATEGORIES,
    liveResource: LiveResource.BOUGHT_ITEMS,
  },
)
