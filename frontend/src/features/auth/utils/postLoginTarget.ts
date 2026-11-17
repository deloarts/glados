import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'

// The closed StartPage vocabulary from /host/values, mapped to sidebar routes.
export const START_PAGE_ROUTES: Record<string, string> = {
  dashboard: '/dashboard',
  todo: '/todo',
  workspace: '/workspace',
  catalogue: '/catalogue/bought-items',
  procurement: '/procurement/orders',
  production: '/production/lots',
  resources: '/resources',
  tools: '/tools',
}

const DEFAULT_START_PAGE_ROUTE = '/dashboard'

/**
 * Resolves the user's `start_page` to a route, falling back to the dashboard
 * for an unknown value or a page behind a disabled feature flag. Shared with
 * the router's `/` redirect so both always agree.
 */
export function resolveStartPageRoute(): string {
  const { user } = useCurrentUserStore()
  const startPage = user?.start_page
  if (!startPage) return DEFAULT_START_PAGE_ROUTE

  const host = useHostStore()
  if (startPage === 'production' && !host.productionPlanningEnabled) {
    return DEFAULT_START_PAGE_ROUTE
  }
  if (startPage === 'todo' && host.todosEnabled === false) {
    return DEFAULT_START_PAGE_ROUTE
  }

  return START_PAGE_ROUTES[startPage] ?? DEFAULT_START_PAGE_ROUTE
}

// Open-redirect guard: `//host` and `/\host` resolve to external origins, so
// only single-leading-slash paths are accepted, anything else counts as none.
function safeRedirect(redirect: unknown): string | null {
  if (typeof redirect !== 'string' || redirect === '') return null
  if (!redirect.startsWith('/')) return null
  if (redirect.startsWith('//') || redirect.startsWith('/\\')) return null
  return redirect
}

/**
 * Where to go after sign-in, shared by all three login success paths. The
 * system user always lands on `/settings`, otherwise a safe `redirect` query
 * wins over the start page. Call only after the current user is refreshed.
 */
export function postLoginTarget(redirectQuery: unknown): string {
  const { user } = useCurrentUserStore()
  if (user?.is_systemuser) return '/settings'

  const redirect = safeRedirect(redirectQuery)
  if (redirect !== null) return redirect

  return resolveStartPageRoute()
}
