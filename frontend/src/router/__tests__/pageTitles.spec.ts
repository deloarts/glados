import { describe, it, expect, vi } from 'vitest'

import { i18n } from '@/core/i18n'

vi.mock('@/features/auth/views/LoginView.vue', () => ({
  default: { name: 'LoginView', template: '<div />' },
}))

import router from '@/router'

// Every route carries a `meta.titleKey` (see usePageTitle, which drives
// document.title from it) that resolves to a real string in en-GB, the
// fallback locale: a missing or unresolved key would otherwise show up as
// the raw dotted key path in the browser tab.
describe('router - page titles', () => {
  const routes = router.getRoutes()

  it('has at least one route to check', () => {
    expect(routes.length).toBeGreaterThan(0)
  })

  it.each(routes.map((route) => [route.name?.toString() ?? route.path, route] as const))(
    '%s has a titleKey that resolves in en-GB',
    (_label, route) => {
      const titleKey = route.meta.titleKey
      expect(typeof titleKey).toBe('string')

      const resolved = i18n.global.t(titleKey as string)
      // vue-i18n returns the key itself when it can't resolve it; this is
      // the check that catches a typo'd key.
      expect(resolved).not.toBe(titleKey)
      expect(resolved.length).toBeGreaterThan(0)
    },
  )
})
