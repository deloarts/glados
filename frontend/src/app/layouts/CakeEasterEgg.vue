<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useCakeProtocol } from '@/core/composables/useCakeProtocol'
import { useEasterEggs } from '@/core/composables/useEasterEggs'
import {
  isCakeWindowOpen,
  isCakeWindowStale,
  rollCakeWindow,
  type CakeWindow,
} from '@/core/utils/cakeSchedule'
import { safeStorage } from '@/core/utils/safeStorage'

// Nothing about the terminal is needed until someone actually asks for cake,
// and it drags in the typewriter and its own stylesheet, so it loads on
// demand, the same way AppLayout defers LotDetailDialog.
const CakeTerminal = defineAsyncComponent(() => import('./CakeTerminal.vue'))

const STORAGE_KEY = 'cakeWindow'
/**
 * Holds the `startsAt` of the window whose cake has already been eaten. The
 * sequence ends by reloading the page, so without this the cake would be
 * sitting in the footer again the moment the app comes back.
 */
const EATEN_KEY = 'cakeEaten'
/**
 * How often the open/closed check re-runs. The window is an hour wide, so a
 * minute of granularity is plenty and costs nothing.
 */
const POLL_MS = 60_000

type Stage = 'idle' | 'ask' | 'confirm'

const { t } = useI18n()
const { phase, isTerminal, run } = useCakeProtocol()
const { cakeSummons } = useEasterEggs()

const stage = ref<Stage>('idle')
const inWindow = ref(false)
/** Set by `?cake=1` or the Konami code; spawns the cake outside its window. */
const forced = ref(false)
/** Declining retires the cake for this tab. */
const dismissed = ref(false)
/**
 * Already eaten in this window; survives the reload the sequence ends with.
 * Gates only the natural appearance; `forced` deliberately ignores it so
 * `?cake=1` and the Konami code stay usable.
 */
const eaten = ref(false)

let currentWindow: CakeWindow | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

const askVisible = computed({
  get: () => stage.value === 'ask',
  set: (value: boolean) => {
    if (!value && stage.value === 'ask') decline()
  },
})

const confirmVisible = computed({
  get: () => stage.value === 'confirm',
  set: (value: boolean) => {
    if (!value && stage.value === 'confirm') decline()
  },
})

const iconVisible = computed(
  () =>
    (forced.value || (inWindow.value && !eaten.value)) &&
    !dismissed.value &&
    phase.value === 'idle',
)

// ── Schedule ────────────────────────────────────────────────────────────────

function readWindow(): CakeWindow | null {
  const raw = safeStorage.get(STORAGE_KEY)
  try {
    return raw ? (JSON.parse(raw) as CakeWindow) : null
  } catch {
    // Corrupt or unreadable: treat it as unrolled and move on.
    return null
  }
}

// Storage full or blocked: the cake just falls back to per-load rolling.
function writeWindow(value: CakeWindow): void {
  safeStorage.set(STORAGE_KEY, JSON.stringify(value))
}

/**
 * Rolls a fresh window at the start of each new week and keeps it, so a
 * reload isn't another go at the dice: the whole point is one appearance a
 * week, not one per page load.
 */
function refreshWindow(): void {
  const now = new Date()
  let window = readWindow()

  if (isCakeWindowStale(window, now)) {
    window = rollCakeWindow(now)
    writeWindow(window)
  }

  currentWindow = window
  inWindow.value = isCakeWindowOpen(window, now)
  eaten.value = Boolean(
    window?.startsAt && safeStorage.get(EATEN_KEY) === String(window.startsAt),
  )
}

// ── Flow ────────────────────────────────────────────────────────────────────

function open(): void {
  stage.value = 'ask'
}

function decline(): void {
  stage.value = 'idle'
  dismissed.value = true
}

function confirm(): void {
  stage.value = 'confirm'
}

function accept(): void {
  stage.value = 'idle'
  dismissed.value = true

  // Recorded before the sequence starts, because the sequence ends by
  // reloading and nothing after this point gets to run.
  // Worst case the cake is offered again after the reload.
  if (currentWindow?.startsAt) safeStorage.set(EATEN_KEY, String(currentWindow.startsAt))

  run()
}

watch(cakeSummons, () => {
  forced.value = true
  dismissed.value = false
})

onMounted(() => {
  refreshWindow()
  pollTimer = setInterval(refreshWindow, POLL_MS)

  if (new URLSearchParams(globalThis.location?.search ?? '').get('cake') === '1') {
    forced.value = true
  }
})

onUnmounted(() => {
  if (pollTimer !== null) clearInterval(pollTimer)
})
</script>

<template>
  <i
    v-if="iconVisible"
    class="mdi mdi-cake-variant cake-icon"
    role="button"
    tabindex="0"
    :aria-label="t('easterEggs.cake.iconLabel')"
    @click="open"
    @keyup.enter="open"
  />

  <Dialog
    v-model:visible="askVisible"
    modal
    :draggable="false"
    :header="t('easterEggs.cake.askHeader')"
    :style="{ width: 'var(--dialog-width-sm)' }"
    :pt="{ root: { 'data-cake-exempt': '' } }"
  >
    <p class="cake-copy">{{ t('easterEggs.cake.askBody') }}</p>
    <template #footer>
      <Button :label="t('common.no')" severity="secondary" text @click="decline" />
      <Button :label="t('common.yes')" @click="confirm" />
    </template>
  </Dialog>

  <Dialog
    v-model:visible="confirmVisible"
    modal
    :draggable="false"
    :header="t('easterEggs.cake.confirmHeader')"
    :style="{ width: 'var(--dialog-width-sm)' }"
    :pt="{ root: { 'data-cake-exempt': '' } }"
  >
    <p class="cake-copy">{{ t('easterEggs.cake.confirmBody') }}</p>
    <template #footer>
      <Button :label="t('common.no')" severity="secondary" text @click="decline" />
      <Button :label="t('common.yes')" severity="danger" @click="accept" />
    </template>
  </Dialog>

  <!-- Teleported out of `.app-shell` on purpose: the collapse transforms the
       shell, and a fixed-position descendant of a transformed ancestor is
       contained by it: the terminal would be squeezed to nothing along with
       everything else. -->
  <Teleport to="body">
    <CakeTerminal v-if="isTerminal" />
  </Teleport>
</template>

<style scoped lang="scss">
.cake-icon {
  position: absolute;
  top: 50%;
  // Immediately left of the live-status icon, which sits at 0.75rem.
  right: 2.25rem;
  transform: translateY(-50%);
  font-size: var(--font-size-md);
  padding-top: var(--space-2);
  cursor: pointer;
  animation: cake-icon-in 1.5s ease-out;

  &:hover {
    opacity: 0.75;
  }
}

.cake-copy {
  margin: 0;
  font-size: var(--font-size-md);
}

@keyframes cake-icon-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .cake-icon {
    animation: none;
  }
}
</style>
