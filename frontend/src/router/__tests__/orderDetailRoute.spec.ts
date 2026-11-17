import { describe, it, expect, vi } from 'vitest'

vi.mock('@/features/auth/views/LoginView.vue', () => ({
  default: { name: 'LoginView', template: '<div />' },
}))

import router from '@/router'

// `/procurement/orders/:id` and `/procurement/orders/timeline` are both real
// destinations that differ only in the shape of the last segment. vue-router
// scores a static segment above a param one, so an unconstrained `:id` would
// out-rank the `/procurement/:section?/:tab?` catch-all that serves the
// timeline and swallow it, rendering the detail page with id="timeline".
// The `(\d+)` constraint in the route is what keeps them apart; these lock it.
//
// resolve() is used rather than push(): it exercises the matcher's ranking
// without running the auth guard, which is covered separately.
describe('order detail route ranking', () => {
  it('matches a numeric id to the detail page', () => {
    const resolved = router.resolve('/procurement/orders/42')

    expect(resolved.name).toBe('OrderDetail')
    expect(resolved.params.id).toBe('42')
  })

  it('leaves /procurement/orders/timeline to the procurement shell', () => {
    const resolved = router.resolve('/procurement/orders/timeline')

    expect(resolved.name).toBe('Procurement')
    expect(resolved.params.section).toBe('orders')
    expect(resolved.params.tab).toBe('timeline')
  })

  it('leaves the bare orders list to the procurement shell', () => {
    const resolved = router.resolve('/procurement/orders')

    expect(resolved.name).toBe('Procurement')
    expect(resolved.params.section).toBe('orders')
  })

  it('does not swallow a non-numeric id', () => {
    const resolved = router.resolve('/procurement/orders/abc')

    expect(resolved.name).toBe('Procurement')
  })
})
