import { createMemoryHistory, createRouter } from 'vue-router'
import type { Router, RouteRecordRaw } from 'vue-router'

/** An empty route component for the paths a spec only navigates to. */
export const RouteStub = { template: '<div />' }

/**
 * A router on in-memory history with the given routes and a trailing
 * catch-all route, so a spec can navigate to any other path without a
 * "no match" warning.
 */
export function makeTestRouter(routes: RouteRecordRaw[] = []): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [...routes, { path: '/:pathMatch(.*)*', component: RouteStub }],
  })
}
