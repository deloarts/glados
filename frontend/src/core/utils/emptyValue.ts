/**
 * The admin-configured symbol shown wherever a value is missing.
 *
 * One entry point for both kinds of caller:
 *
 * - Components import it and call it straight from the template,
 *   `{{ x ?? getEmptyPlaceholder() }}`. `<script setup>` exposes imports to
 *   the template, and the call reads the store during render, so Vue tracks it
 *   and every site updates when an admin changes the setting.
 * - Plain functions (formatDecimal, formatISODate, formatPrice) call it too.
 *   They are not components and cannot hold a computed; reading the store
 *   lazily at call time gives them the current value without turning them into
 *   composables.
 *
 * The store is resolved lazily on purpose: this module is imported by
 * core/utils, which is loaded long before `app.use(pinia)` runs. Calling
 * useHostStore() at module scope would throw "no active Pinia".
 */
import { useHostStore } from '@/core/host/stores/hostStore'

// Matches the backend's own default, so a formatter called before
// /host/capabilities answers renders the same symbol the server would send.
const FALLBACK = '-'

export function getEmptyPlaceholder(): string {
  try {
    return useHostStore().emptyPlaceholder
  } catch {
    // No active Pinia, a formatter called from a unit test or from module
    // init. The fallback keeps those callers working rather than throwing.
    return FALLBACK
  }
}
