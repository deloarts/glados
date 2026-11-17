/**
 * OpenVue's `DataTable` emits both `row-click` and `row-select` (or
 * `row-unselect`) synchronously for the *same* interaction once
 * `selectionMode` is set: a mouse click and a keyboard Enter both route
 * through the table's internal `onRowClick`, which always emits
 * `row-click`, and for a row transitioning from unselected to selected,
 * emits `row-select` right after, in the same call stack.
 *
 * Binding the same "open this row" handler to both events (so Enter and
 * click behave identically) would therefore run it twice
 * for a single click. `useRowOpenGuard` makes that idempotent: `guard(key,
 * fn)` runs `fn` immediately, then ignores a second call for the same
 * `key` until the current synchronous dispatch has finished (cleared on
 * the next microtask, after both OpenVue emits have had a chance to
 * fire). A later, separate interaction on the same row still runs `fn`.
 */
export function useRowOpenGuard<TKey = unknown>() {
  let pendingKey: TKey | null = null
  let pending = false

  function guard(key: TKey, fn: () => void): void {
    if (pending && pendingKey === key) return
    pending = true
    pendingKey = key
    queueMicrotask(() => {
      pending = false
      pendingKey = null
    })
    fn()
  }

  return { guard }
}
