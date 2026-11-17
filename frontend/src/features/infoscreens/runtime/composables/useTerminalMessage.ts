import { onScopeDispose, ref, watch } from 'vue'
import type { Ref } from 'vue'

import { parseBackendTimestamp } from '@/core/utils/dates'

import type { TerminalMessage } from '../types/infoscreenFeed'

// The longest delay a browser timer takes; a later end is reached in steps.
const MAX_TIMER_MS = 2_147_483_647

/**
 * The message to show from the one the backend sends, until its
 * `show_until`. The end is kept by a timer on the device clock, so the
 * message goes away on time without another request.
 */
export function useTerminalMessage(source: () => TerminalMessage | null | undefined): Ref<TerminalMessage | null> {
  const visible = ref<TerminalMessage | null>(null)
  let timer: ReturnType<typeof setTimeout> | null = null

  function clearTimer(): void {
    if (timer) clearTimeout(timer)
    timer = null
  }

  function show(message: TerminalMessage | null): void {
    clearTimer()
    if (!message) {
      visible.value = null
      return
    }
    const remaining = parseBackendTimestamp(message.show_until).getTime() - Date.now()
    if (!(remaining > 0)) {
      visible.value = null
      return
    }
    visible.value = message
    timer = setTimeout(() => show(message), Math.min(remaining, MAX_TIMER_MS))
  }

  watch(source, (message) => show(message ?? null), { immediate: true })
  onScopeDispose(clearTimer)

  return visible
}
