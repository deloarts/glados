import { onScopeDispose, ref, watch } from 'vue'
import type { Ref } from 'vue'

/**
 * Steps through a screen's pages every `seconds`, starting over after the
 * last one. A screen with one page never rotates. A change of the page count
 * or the interval restarts the timer, and an index left beyond the last page
 * goes back to the first.
 */
export function usePageRotation(pageCount: Ref<number>, seconds: Ref<number>) {
  const pageIndex = ref(0)
  let timer: ReturnType<typeof setInterval> | null = null

  function clear(): void {
    if (timer) clearInterval(timer)
    timer = null
  }

  watch(
    [pageCount, seconds],
    ([count, interval]) => {
      clear()
      if (pageIndex.value >= count) pageIndex.value = 0
      if (count <= 1 || interval <= 0) return
      timer = setInterval(() => {
        pageIndex.value = (pageIndex.value + 1) % pageCount.value
      }, interval * 1000)
    },
    { immediate: true },
  )

  onScopeDispose(clear)

  return { pageIndex }
}
