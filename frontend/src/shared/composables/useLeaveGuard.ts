import { getCurrentInstance, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import type { RouteLocationNormalized } from 'vue-router'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'

export interface LeaveGuardOptions {
  /** Whether leaving now would leave unsaved changes behind. */
  dirty: () => boolean
  /** Asks the user; resolves true to leave. */
  confirm: () => Promise<boolean>
  /**
   * Also guards a change of the route's own params or query, such as another
   * revision opened on the same page. Return false for a change that keeps
   * the changes on screen.
   */
  updates?: boolean | ((to: RouteLocationNormalized, from: RouteLocationNormalized) => boolean)
}

/**
 * Asks before a page with unsaved changes is left: inside the app through
 * `confirm`, and on reload or closing the browser tab through the browser's
 * own prompt. A navigation after the session ended, such as the redirect to
 * the login page when it expired, goes through unasked, since nobody is left
 * to ask. `allowNext()` lets the page's own next navigation pass, for a step
 * that already asked or left nothing to lose.
 */
export function useLeaveGuard(options: LeaveGuardOptions) {
  const currentUserStore = useCurrentUserStore()
  let allowed = false

  function mustAsk(): boolean {
    return currentUserStore.user != null && options.dirty()
  }

  function guard(): boolean | Promise<boolean> {
    if (allowed) {
      allowed = false
      return true
    }
    return mustAsk() ? options.confirm() : true
  }

  onBeforeRouteLeave(guard)
  if (options.updates) {
    const updates = options.updates
    onBeforeRouteUpdate((to, from) => (updates === true || updates(to, from) ? guard() : true))
  }

  function onBeforeUnload(event: BeforeUnloadEvent): void {
    if (!mustAsk()) return
    event.preventDefault()
    // Older browsers show the prompt only with a return value set.
    event.returnValue = ''
  }

  if (typeof window !== 'undefined' && getCurrentInstance()) {
    window.addEventListener('beforeunload', onBeforeUnload)
    onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))
  }

  return {
    /** Call right before the navigation; a navigation that never happens does not keep the pass. */
    allowNext(): void {
      allowed = true
      setTimeout(() => (allowed = false), 0)
    },
  }
}
