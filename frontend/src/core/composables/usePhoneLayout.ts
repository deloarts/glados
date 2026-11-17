import { computed, inject, ref, watch } from 'vue'
import { routeLocationKey } from 'vue-router'
import type { RouteLocationNormalizedLoaded, RouteRecordNameGeneric } from 'vue-router'
import { createSharedComposable, useMediaQuery } from '@vueuse/core'

/**
 * The phone breakpoint, `$bp-sm` in `_breakpoints.scss`. A media query reads
 * rem against the browser default rather than the pinned root size, so 48rem
 * is 768px here just as it is in the stylesheets.
 */
export const PHONE_MEDIA_QUERY = '(max-width: 48rem)'

/**
 * What a route offers on a phone: the whole page, or only the tabs that one
 * of its params names. A route without a scope is built for the desktop.
 */
export type PhoneScope = true | { param: string; tabs: readonly string[] }

declare module 'vue-router' {
  interface RouteMeta {
    phone?: PhoneScope
  }
}

type PhoneRoute = Pick<RouteLocationNormalizedLoaded, 'matched' | 'meta' | 'params'>

/**
 * Whether a route is built for a phone. A tab route without its param shows
 * the view's default tab, and a view whose desktop default is not one of its
 * phone tabs picks a phone tab itself, so a missing param counts as offered.
 * A path that matches no route renders nothing, so it is never gated.
 */
export function offeredOnPhone(route: PhoneRoute): boolean {
  if (route.matched.length === 0) return true
  const scope = route.meta.phone
  if (scope === true) return true
  if (!scope) return false
  const tab = route.params[scope.param]
  return typeof tab !== 'string' || tab === '' || scope.tabs.includes(tab)
}

/**
 * The phone layout state of the signed-in app. `isPhone` follows the screen
 * width. `phoneMode` is what views trim themselves by: it is off on a desktop
 * and on a page the user asked to see in full anyway, which lasts until they
 * leave that route.
 *
 * Shared components such as the controls bar read it too, and those also
 * mount without a router (in a spec, say). Without one every page counts as
 * offered, so only the screen width applies.
 */
export const usePhoneLayout = createSharedComposable(() => {
  const route: RouteLocationNormalizedLoaded | null = inject(routeLocationKey, null)
  const isPhone = useMediaQuery(PHONE_MEDIA_QUERY)
  const desktopRoute = ref<RouteRecordNameGeneric | null>(null)

  watch(
    () => route?.name,
    (name) => {
      if (name !== desktopRoute.value) desktopRoute.value = null
    },
  )

  const phoneMode = computed(
    () => isPhone.value && (desktopRoute.value === null || desktopRoute.value !== route?.name),
  )

  const showDesktopNotice = computed(
    () => phoneMode.value && route !== null && !offeredOnPhone(route),
  )

  /** Whether a tab of the current route appears in its tab strip. */
  function tabOffered(tab: string): boolean {
    if (!phoneMode.value || route === null) return true
    const scope = route.meta.phone
    return scope === true || (scope !== undefined && scope.tabs.includes(tab))
  }

  function showDesktopAnyway(): void {
    desktopRoute.value = route?.name ?? null
  }

  return { isPhone, phoneMode, showDesktopNotice, tabOffered, showDesktopAnyway }
})
