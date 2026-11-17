/**
 * Picture endpoints of the made, bought and source item catalogues. Each kind
 * serves the same routes under its own prefix, plus a flat `-pictures` route
 * naming the picture shown for many items at once (a flat
 * `/<items>/pictures` would be swallowed by `GET /<items>/{item_id}`).
 */
import type { Schemas } from '@/core/api/generated'
import { postFile } from '@/core/api/postFile'
import { webApi } from '@/core/api/webRequest'

export type ItemPicture = Schemas['ItemPictureResponse']
export type ItemPictureInUse = Schemas['ItemPictureInUseResponse']
export type ItemPictureSource = Schemas['ItemPictureSource']
export type ItemPictureVariant = 'image' | 'thumbnail'

/** The order in which the picture shown for an item is chosen. */
export const PICTURE_SOURCES: readonly ItemPictureSource[] = [
  'picture',
  'data_portal',
  'cad_rendering',
]

const PICTURE_ROUTES = {
  made: {
    list: '/made-items/{item_id}/pictures',
    photo: '/made-items/{item_id}/pictures/picture',
    blob: '/made-items/{item_id}/pictures/{source}/{variant}',
    batch: '/made-items-pictures/',
  },
  bought: {
    list: '/bought-items/{item_id}/pictures',
    photo: '/bought-items/{item_id}/pictures/picture',
    blob: '/bought-items/{item_id}/pictures/{source}/{variant}',
    batch: '/bought-items-pictures/',
  },
  source: {
    list: '/source-items/{item_id}/pictures',
    photo: '/source-items/{item_id}/pictures/picture',
    blob: '/source-items/{item_id}/pictures/{source}/{variant}',
    batch: '/source-items-pictures/',
  },
} as const

export type PictureItemKind = keyof typeof PICTURE_ROUTES

export interface ItemPicturesApi {
  list(itemId: number): Promise<ItemPicture[]>
  /** The picture shown for each listed item that has one. */
  listInUse(itemIds: number[]): Promise<ItemPictureInUse[]>
  getBlob(itemId: number, source: ItemPictureSource, variant: ItemPictureVariant): Promise<Blob>
  /** Uploads the photo, which replaces only the previous photo. */
  upload(itemId: number, file: File): Promise<ItemPicture>
  /** Deletes the photo; the Data Portal picture and CAD rendering stay. */
  removePhoto(itemId: number): Promise<void>
}

export function createItemPicturesApi(kind: PictureItemKind): ItemPicturesApi {
  const routes = PICTURE_ROUTES[kind]

  return {
    async list(itemId) {
      return (await webApi.get(routes.list, { path: { item_id: itemId } })) as ItemPicture[]
    },

    async listInUse(itemIds) {
      if (itemIds.length === 0) return []
      return (await webApi.get(routes.batch, {
        query: { item_ids: itemIds },
      })) as ItemPictureInUse[]
    },

    async getBlob(itemId, source, variant) {
      return (await webApi.get(routes.blob, {
        path: { item_id: itemId, source, variant },
        config: { responseType: 'blob' },
      })) as Blob
    },

    async upload(itemId, file) {
      return (await postFile(routes.list, file, { path: { item_id: itemId } })) as ItemPicture
    },

    async removePhoto(itemId) {
      await webApi.delete(routes.photo, { path: { item_id: itemId } })
    },
  }
}
