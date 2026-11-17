import { LiveResource } from '@/core/realtime/resources'
import { createItemPicturesApi, createItemPicturesStore } from '@/shared/pictures'

export const useBoughtItemPicturesStore = createItemPicturesStore(
  'boughtItemPictures',
  createItemPicturesApi('bought'),
  LiveResource.BOUGHT_ITEMS,
)
