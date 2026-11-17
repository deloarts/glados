import type { ResolvePublicIdResponse } from './types/resolvePublicIdResponse'

// Maps a resolved resource to the route that lists it, following each shell
// view's tabs. Production orders map to the queue tab.
const RESOURCE_ROUTES: Record<string, string> = {
  products: '/workspace/products',
  projects: '/workspace/projects',
  customers: '/resources/customers',
  suppliers: '/resources/suppliers',
  contacts: '/resources/contacts',
  'article-groups': '/resources/article-groups',
  'fabrication-methods': '/resources/fabrication-methods',
  'source-item-types': '/resources/source-item-types',
  'production-machines': '/resources/machines',
  'production-machine-pools': '/resources/machine-pools',
  'bought-items': '/catalogue/bought-items',
  'made-items': '/catalogue/made-items',
  'source-items': '/catalogue/source-items',
  orders: '/procurement/orders',
  'production-lots': '/production/lots',
  'production-orders': '/production/queue',
  users: '/settings/users',
  calculations: '/calculations',
  checklists: '/checklists',
  sequences: '/workspace/products',
}

// Resources with a page for a single record; the rest fall back to their
// list.
const RESOURCE_DETAIL_ROUTES: Record<string, (id: number) => string> = {
  orders: (id) => `/procurement/orders/${id}`,
  projects: (id) => `/workspace/projects/${id}`,
  'bought-items': (id) => `/catalogue/bought-items/${id}`,
  'made-items': (id) => `/catalogue/made-items/${id}`,
  'source-items': (id) => `/catalogue/source-items/${id}`,
  products: (id) => `/workspace/products/${id}`,
  'production-lots': (id) => `/production/lots/${id}`,
  'production-orders': (id) => `/production/orders/${id}`,
  calculations: (id) => `/calculations/${id}`,
  checklists: (id) => `/checklists/${id}`,
  sequences: (id) => `/sequences/${id}`,
  // The contacts tab opens the contact's dialog.
  contacts: (id) => `/resources/contacts?contact=${id}`,
  // Looks up the meeting's project or product and opens its page there.
  meetings: (id) => `/meetings/${id}`,
}

export function routeForResource(resource: string): string | null {
  return RESOURCE_ROUTES[resource] ?? null
}

/**
 * The best route for a resolved public id: the record's own page where one
 * exists, otherwise the list its resource lives in.
 */
export function routeForResolved(resolved: ResolvePublicIdResponse): string | null {
  return RESOURCE_DETAIL_ROUTES[resolved.resource]?.(resolved.id) ?? routeForResource(resolved.resource)
}
