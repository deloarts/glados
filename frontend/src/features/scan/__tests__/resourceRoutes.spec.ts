import { describe, it, expect } from 'vitest'

import { routeForResolved, routeForResource } from '../resourceRoutes'

function resolved(resource: string, id: number) {
  return { resource, id, public_id: '00000000-0000-0000-0000-000000000000' }
}

describe('routeForResolved', () => {
  it('routes a scanned order to its own page, not the orders list', () => {
    expect(routeForResolved(resolved('orders', 42))).toBe('/procurement/orders/42')
  })

  it('routes a scanned project to its own page', () => {
    expect(routeForResolved(resolved('projects', 7))).toBe('/workspace/projects/7')
  })

  it('routes a scanned bought item to its own page', () => {
    expect(routeForResolved(resolved('bought-items', 15))).toBe('/catalogue/bought-items/15')
  })

  it('routes a scanned made item to its own page', () => {
    expect(routeForResolved(resolved('made-items', 23))).toBe('/catalogue/made-items/23')
  })

  it('routes a scanned source item to its own page', () => {
    expect(routeForResolved(resolved('source-items', 31))).toBe('/catalogue/source-items/31')
  })

  it('routes a scanned product to its own page', () => {
    expect(routeForResolved(resolved('products', 5))).toBe('/workspace/products/5')
  })

  it('routes a scanned production lot to its own page', () => {
    expect(routeForResolved(resolved('production-lots', 9))).toBe('/production/lots/9')
  })

  it('routes a scanned production order to its own page', () => {
    expect(routeForResolved(resolved('production-orders', 12))).toBe('/production/orders/12')
  })

  it('falls back to the list for a resource with no detail page', () => {
    expect(routeForResolved(resolved('suppliers', 3))).toBe('/resources/suppliers')
  })

  it('returns null for a resource with no frontend route at all', () => {
    expect(routeForResolved(resolved('printers', 1))).toBeNull()
  })
})

describe('routeForResource', () => {
  it('still answers with the list route', () => {
    expect(routeForResource('orders')).toBe('/procurement/orders')
    expect(routeForResource('nonsense')).toBeNull()
  })

  it('routes production orders to the queue tab that lists them', () => {
    expect(routeForResource('production-orders')).toBe('/production/queue')
  })
})
