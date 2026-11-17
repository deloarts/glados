import type { Schemas } from '@/core/api/generated'

// Geometry lives on the made items, so a product has reference images,
// specification documents and the images of its devices.
export type ProductFileCategory = Schemas['ProductFileCategory']

export const SINGLETON_FILE_CATEGORIES: ProductFileCategory[] = ['thumbnail', 'image', 'device_overview']

export type ProductFile = Schemas['ProductFileResponse']

/** A product as other records embed it, such as the product of a project. */
export type ProductBaseResponse = Schemas['ProductResponse']

/** A product as the product endpoints return it, with the machine data for the CE assessment. */
export type ProductResponse = Schemas['ProductWebResponse']
