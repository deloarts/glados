import { ref, type Ref } from 'vue'

/**
 * The show/hide-plus-payload pair repeated by hand across every table that
 * pops a secondary dialog for a specific row or item: a `target` ref
 * holding whatever the dialog needs to render, and a `visible` ref driving
 * its `v-model:visible`. `open(value)` sets both in one call; `close()`
 * only hides. The target is left in place so a closing transition still
 * has data to render, matching every hand-rolled version this replaces
 * (none of them cleared their target ref on close either).
 */
export function useDialogTarget<T>() {
  const target = ref<T | null>(null) as Ref<T | null>
  const visible = ref(false)

  function open(value: T): void {
    target.value = value
    visible.value = true
  }

  function close(): void {
    visible.value = false
  }

  return { target, visible, open, close }
}
