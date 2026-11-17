// Public barrel of the scan feature. Other code imports through here
// (enforced by eslint).

export { useScan } from './composables/useScan'
export { isPublicId, publicIdFromCode } from './publicId'
export { resolvePublicId } from './api/resolvePublicId'
export { routeForResolved, routeForResource } from './resourceRoutes'

export type { ResolvePublicIdResponse } from './types/resolvePublicIdResponse'
