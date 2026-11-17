import { ref, type Ref } from 'vue'

/**
 * The "which rows have an async action in flight" `Set` boilerplate every
 * table with per-row mutations repeats: add the id before starting, remove
 * it in a `finally` so a thrown error still clears it, and always through a
 * *new* `Set`, since mutating the existing one in place wouldn't trigger the
 * ref's reactivity. `isPending(id)` is what a row's `:loading` binding
 * reads; `run(id, fn)` wraps an action with the add/remove bookkeeping and
 * re-throws whatever `fn` throws, same as the hand-rolled try/finally
 * blocks this replaces.
 */
export function useRowMutationState<Id>() {
  const pending = ref<Set<Id>>(new Set()) as Ref<Set<Id>>

  function isPending(id: Id): boolean {
    return pending.value.has(id)
  }

  async function run(id: Id, fn: () => Promise<void>): Promise<void> {
    pending.value = new Set([...pending.value, id])
    try {
      await fn()
    } finally {
      pending.value = new Set([...pending.value].filter((pendingId) => pendingId !== id))
    }
  }

  return { pending, isPending, run }
}
