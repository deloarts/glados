import { LiveResource } from '@/core/realtime/resources'
import { createItemPicturesApi, createItemPicturesStore } from '@/shared/pictures'

export const useSourceItemPicturesStore = createItemPicturesStore(
  'sourceItemPictures',
  createItemPicturesApi('source'),
  LiveResource.SOURCE_ITEMS,
)
