/**
 * File attachment endpoints shared by every aggregate that carries files: the
 * bought, made and source item catalogues, products, orders, production
 * orders and the supplier entries of quote requests. Each backend serves the
 * same routes under its own owner prefix. The item catalogues and products
 * also have a flat `-files` route for fetching many owners' files at once (a
 * flat `/<items>/files` would be swallowed by `GET /<items>/{item_id}`), which
 * `createFilesApi` adds as `listForItems`. `createOwnerFilesApi` covers the per-owner routes alone.
 */
import { postFile } from '@/core/api/postFile'
import { webApi } from '@/core/api/webRequest'

const FILE_ROUTES = {
  bought: { owner: '/bought-items/{item_id}', param: 'item_id', batch: '/bought-items-files' },
  made: { owner: '/made-items/{item_id}', param: 'item_id', batch: '/made-items-files' },
  source: { owner: '/source-items/{item_id}', param: 'item_id', batch: '/source-items-files' },
  product: { owner: '/products/{product_id}', param: 'product_id', batch: '/products-files/' },
  order: { owner: '/orders/{order_id}', param: 'order_id' },
  productionOrder: { owner: '/production-orders/{order_id}', param: 'order_id' },
  quoteSupplier: { owner: '/quote-request-suppliers/{row_id}', param: 'row_id' },
} as const

type FileRoutes = typeof FILE_ROUTES

export type FileOwnerKind = keyof FileRoutes

/** The owner kinds that have a batch route for many owners at once. */
export type FileItemKind = {
  [K in FileOwnerKind]: FileRoutes[K] extends { batch: string } ? K : never
}[FileOwnerKind]

type OwnerParam = FileRoutes[FileOwnerKind]['param']

export interface FilesApiTypes {
  file: unknown
  category: string
}

interface OwnerFilesApi<T extends FilesApiTypes> {
  list(ownerId: number): Promise<T['file'][]>
  upload(ownerId: number, file: File, category: T['category']): Promise<T['file']>
  remove(ownerId: number, fileId: number): Promise<void>
  getBlob(ownerId: number, fileId: number): Promise<Blob>
}

interface BatchFilesApi<T extends FilesApiTypes> {
  /**
   * One request for many owners, for views rendering a thumbnail per row.
   * Returns a flat list; each file carries its own owner id, so callers group.
   */
  listForItems(ownerIds: number[]): Promise<T['file'][]>
}

// The owner templates name different path parameters, so the compiler sees a
// union of parameter objects. The record claims every name to satisfy each
// member; only the one the chosen template names is read when the URL is built.
function ownerPath(param: OwnerParam, ownerId: number): Record<OwnerParam, number> {
  return { [param]: ownerId } as Record<OwnerParam, number>
}

/** The per-owner file routes, for every kind including those without a batch route. */
export function createOwnerFilesApi<T extends FilesApiTypes>(
  kind: FileOwnerKind,
): OwnerFilesApi<T> {
  const { owner, param } = FILE_ROUTES[kind]

  return {
    async list(ownerId) {
      return (await webApi.get(`${owner}/files`, {
        path: ownerPath(param, ownerId),
      })) as T['file'][]
    },

    async upload(ownerId, file, category) {
      return (await postFile(`${owner}/files`, file, {
        path: ownerPath(param, ownerId),
        fields: { category },
      })) as T['file']
    },

    async remove(ownerId, fileId) {
      await webApi.delete(`${owner}/files/{file_id}`, {
        path: { ...ownerPath(param, ownerId), file_id: fileId },
      })
    },

    async getBlob(ownerId, fileId) {
      return (await webApi.get(`${owner}/files/{file_id}`, {
        path: { ...ownerPath(param, ownerId), file_id: fileId },
        config: { responseType: 'blob' },
      })) as Blob
    },
  }
}

/** The per-owner file routes plus the batch route, for the kinds that have one. */
export function createFilesApi<T extends FilesApiTypes>(
  kind: FileItemKind,
): OwnerFilesApi<T> & BatchFilesApi<T> {
  const { batch } = FILE_ROUTES[kind]

  return {
    ...createOwnerFilesApi<T>(kind),

    async listForItems(ownerIds) {
      if (ownerIds.length === 0) return []
      return (await webApi.get(batch, { query: { item_ids: ownerIds } })) as T['file'][]
    },
  }
}
