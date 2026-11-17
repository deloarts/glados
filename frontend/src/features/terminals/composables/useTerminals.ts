import { computed, onScopeDispose, ref } from 'vue'

import { usePermissions } from '@/core/composables/usePermissions'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { Permission } from '@/core/auth/permissions'
import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { createTokenApi } from '@/shared/api/createTokenApi'
import { getActiveTerminalBroadcasts } from '../api/terminalBroadcastsApi'
import { getScreenOptions, getTerminals } from '../api/terminalsApi'
import { activeBroadcasts } from '../utils/terminalBroadcasts'
import { isPending } from '../utils/terminalStatus'

import type {
  TerminalBroadcastResponse,
  TerminalResponse,
  TerminalScreenOption,
} from '../types/terminalResponse'

/** How often the offline badges are re-evaluated without any live signal. */
const CLOCK_TICK_MS = 30_000

const apiKeysApi = createTokenApi('/admin/api-keys')

/**
 * The state of the terminals tab: every terminal, split into the ones
 * waiting for approval and the enrolled ones, the screens a terminal can be
 * given, the messages shown on terminals right now, and whether a usable
 * terminal key exists. Terminals, screens and messages follow live signals;
 * a clock ticks so a terminal turns offline and a message ends on screen
 * even when nothing else changes.
 */
export function useTerminals() {
  const { hasPermission } = usePermissions()
  const { toastOnError } = useErrorToast()

  const terminals = ref<TerminalResponse[]>([])
  const screens = ref<TerminalScreenOption[]>([])
  const allBroadcasts = ref<TerminalBroadcastResponse[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  watchLoadingBar(loading)

  // Null while unknown: the key list needs manage:api_keys, and without it
  // the tab cannot tell whether a key exists, so it shows no hint.
  const hasTerminalKey = ref<boolean | null>(null)

  const now = ref(Date.now())
  const clock = setInterval(() => {
    now.value = Date.now()
  }, CLOCK_TICK_MS)
  onScopeDispose(() => clearInterval(clock))

  const pending = computed(() => terminals.value.filter(isPending))
  const enrolled = computed(() => terminals.value.filter((terminal) => !isPending(terminal)))
  const approved = computed(() =>
    terminals.value.filter((terminal) => terminal.status === 'approved'),
  )
  const broadcasts = computed(() => activeBroadcasts(allBroadcasts.value, now.value))

  async function loadTerminals(): Promise<void> {
    terminals.value = await getTerminals()
    now.value = Date.now()
  }

  async function loadScreens(): Promise<void> {
    screens.value = await getScreenOptions()
  }

  async function loadBroadcasts(): Promise<void> {
    allBroadcasts.value = await getActiveTerminalBroadcasts()
  }

  async function loadKeyState(): Promise<void> {
    if (!hasPermission(Permission.MANAGE_API_KEYS)) {
      hasTerminalKey.value = null
      return
    }
    try {
      // One usable terminal key is enough to know that one exists.
      const page = await apiKeysApi.list({ kind: 'terminal', expiry: 'unexpired', limit: 1 })
      hasTerminalKey.value = page.total > 0
    } catch {
      hasTerminalKey.value = null
    }
  }

  async function load(): Promise<void> {
    loading.value = true
    try {
      await Promise.all([loadTerminals(), loadScreens(), loadBroadcasts(), loadKeyState()])
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  /** Puts a row the server just returned in place, so an action shows at once. */
  function upsert(terminal: TerminalResponse): void {
    const index = terminals.value.findIndex((row) => row.id === terminal.id)
    if (index === -1) terminals.value = [...terminals.value, terminal]
    else terminals.value = terminals.value.map((row) => (row.id === terminal.id ? terminal : row))
  }

  function remove(terminalId: number): void {
    terminals.value = terminals.value.filter((row) => row.id !== terminalId)
  }

  /** Puts a message the server just returned in place, or drops it once it has ended. */
  function upsertBroadcast(broadcast: TerminalBroadcastResponse): void {
    const others = allBroadcasts.value.filter((row) => row.id !== broadcast.id)
    allBroadcasts.value = broadcast.ended_at === null ? [broadcast, ...others] : others
  }

  useLiveRefresh([LiveResource.TERMINALS], loadTerminals)
  // A renamed or archived screen changes the screen names in the rows too.
  useLiveRefresh([LiveResource.INFOSCREENS], () => Promise.all([loadScreens(), loadTerminals()]))
  useLiveRefresh([LiveResource.TERMINAL_BROADCASTS], loadBroadcasts)
  // The display power of a terminal follows the default schedule too.
  useLiveRefresh([LiveResource.INFOSCREEN_DEFAULTS], loadTerminals)

  function start(): void {
    load().catch(toastOnError())
  }

  return {
    terminals,
    pending,
    enrolled,
    approved,
    screens,
    broadcasts,
    loading,
    loaded,
    hasTerminalKey,
    now,
    load,
    start,
    upsert,
    remove,
    upsertBroadcast,
    loadTerminals,
    loadKeyState,
  }
}
