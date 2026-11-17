import { LiveResource } from '@/core/realtime/resources'
import { createItemPicturesApi, createItemPicturesStore } from '@/shared/pictures'

export const useMadeItemPicturesStore = createItemPicturesStore(
  'madeItemPictures',
  createItemPicturesApi('made'),
  LiveResource.MADE_ITEMS,
)
