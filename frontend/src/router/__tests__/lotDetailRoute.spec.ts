import { describe, it, expect, vi } from 'vitest'

vi.mock('@/features/auth/views/LoginView.vue', () => ({
  default: { name: 'LoginView', template: '<div />' },
}))

import router from '@/router'

// `/production/lots/:id` and `/production/lots/timeline` are both real
// destinations that differ only in the shape of the last segment. vue-router
// scores a static segment above a param one, so an unconstrained `:id` would
// out-rank `/production/lots/timeline` and swallow it, rendering the detail
// page with id="timeline".
// The `(\d+)` constraint in the route is what keeps them apart; these lock it.
//
// resolve() is used rather than push(): it exercises the matcher's ranking
// without running the auth guard, which is covered separately.
describe('lot detail route ranking', () => {
  it('matches a numeric id to the detail page', () => {
    const resolved = router.resolve('/production/lots/42')

    expect(resolved.name).toBe('LotDetail')
    expect(resolved.params.id).toBe('42')
  })

  it('leaves /production/lots/timeline to its own route', () => {
    const resolved = router.resolve('/production/lots/timeline')

    expect(resolved.name).toBe('ProductionLotsTimeline')
  })

  it('leaves the bare lots list to the production lots route', () => {
    const resolved = router.resolve('/production/lots')

    expect(resolved.name).toBe('ProductionLots')
  })

  it('does not match a non-numeric id to any route', () => {
    const resolved = router.resolve('/production/lots/abc')

    // Observed: unlike /procurement, the /production/:tab? catch-all only
    // spans one segment past /production, so it doesn't reach a 3-segment
    // path like this one: nothing matches at all (matched: [], name: undefined).
    expect(resolved.name).toBeUndefined()
    expect(resolved.matched.length).toBe(0)
  })
})
