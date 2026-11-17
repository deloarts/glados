<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, watch } from 'vue'
import { START_LOCATION, useRoute, useRouter } from 'vue-router'
import { useWakeLock } from '@vueuse/core'

import AppLayout from '@/app/layouts/AppLayout.vue'
import AuthLayout from '@/app/layouts/AuthLayout.vue'
import KioskLayout from '@/app/layouts/KioskLayout.vue'
import LiveConnectionHandler from '@/shared/components/handlers/LiveConnectionHandler.vue'
import ToastHandler from '@/shared/components/handlers/ToastHandler.vue'
import ConfirmHandler from '@/shared/components/handlers/ConfirmHandler.vue'
import { AnnouncementsHandler } from '@/features/announcements'

import {
  APERTURE_PRESET,
  APERTURE_PRIMARY,
  initEasterEggs,
  useEasterEggs,
} from '@/core/composables/useEasterEggs'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { prefersDarkMode, useLayoutStore } from '@/core/stores/layoutStore'
import { useOpenVueLocale } from '@/core/composables/useOpenVueLocale'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import {
  paintRememberedScreenLanguage,
  paintRememberedScreenTheme,
  repaintScreenLanguage,
} from '@/core/terminal/deviceScreenMemory'
// Deep import rather than the production feature's barrel, which re-exports
// components and would pull them all into the entry chunk. App-lifetime
// subscription must outlive any single AutoPlanDialog instance, so it is
// wired here rather than inside the dialog or the shared
// LiveConnectionHandler (which must stay feature-free).
// eslint-disable-next-line no-restricted-imports -- composable only, see above
import { useAutoPlanRunLiveSync } from '@/features/production/composables/useAutoPlanRunLiveSync'

/**
 * What to fall back to when aperture mode is switched off and the user has no
 * saved preset of their own.
 */
const DEFAULT_PRESET = 'Aura'

const route = useRoute()
const router = useRouter()
// Until the first navigation has resolved, the route is the router's start
// location, which has no layout yet: rendering one would put the app shell
// on a wall display for the first frames, so nothing is rendered instead.
const firstRouteResolved = computed(() => router.currentRoute.value !== START_LOCATION)
const isAuthRoute = computed(() => route.meta.layout === 'auth')
// Wall displays and the infoscreen preview: full viewport, no app shell.
const isKioskRoute = computed(() => route.meta.layout === 'kiosk')

const { release } = useWakeLock()
const layoutStore = useLayoutStore()
const { initDefaultTheme } = layoutStore
const publicBrandingStore = usePublicBrandingStore()
const currentUserStore = useCurrentUserStore()
const { apertureMode } = useEasterEggs()

// A wall display starts in the theme and language of the screen it showed
// last, set before the first render, since its first feed takes a moment.
// Without a remembered language it shows the tenant default the public
// branding sets. The address is resolved directly because the first
// navigation has not run yet.
function opensOnDevice(): boolean {
  const opened = router.resolve(router.options.history.location)
  return opened.meta.layout === 'kiosk' && opened.meta.requiresAuth === false
}
const startsOnDevice = opensOnDevice()
const startsInScreenTheme = startsOnDevice && paintRememberedScreenTheme()
if (startsOnDevice) paintRememberedScreenLanguage()

// Aperture mode swaps the OpenVue preset and forces dark mode for the
// duration, and puts the user's own back when it is switched off. Nothing here
// is written server-side: preset/primary/surface/dark-mode are only persisted
// from the account page and the sidebar toggle, and the egg must never end up
// in someone's saved theme.
// The saved values are watched alongside the flag because currentUserStore's
// refresh() lands asynchronously: without them, a tab that boots with aperture
// mode already on would have applyUserTheme quietly put the normal theme back
// a moment later.
watch(
  [
    apertureMode,
    () => currentUserStore.user?.theme_preset,
    () => currentUserStore.user?.theme_dark_mode,
  ],
  ([on, savedPreset, savedDarkMode]) => {
    // applyPreset, not setPreset: swapping the preset on its own would drop the
    // user's primary/surface back to the preset's own defaults. The red is
    // passed as an override so it paints over the user's primary rather than
    // replacing it; switching the mode off has to put their colour back.
    layoutStore.applyPreset(
      on ? APERTURE_PRESET : (savedPreset ?? DEFAULT_PRESET),
      on ? APERTURE_PRIMARY : undefined,
    )
    // Aperture Science does not do daylight. Unlike the primary this is set
    // rather than painted, so the sidebar's moon/sun toggle keeps telling the
    // truth while the mode is on; what it goes back to is the user's saved
    // preference, or the OS one for anybody without a saved theme.
    layoutStore.setDarkMode(on ? true : (savedDarkMode ?? prefersDarkMode()))
  },
)

// Drives every DatePicker's input format from the user's preference, see the
// composable for why this lives at the root.
useOpenVueLocale()

// App-wide auto-plan run subscription: outlives any single
// AutoPlanDialog/trigger-button instance so anyRunActive/activeRun stay
// correct app-wide even with no dialog mounted anywhere.
useAutoPlanRunLiveSync()

onBeforeUnmount(() => {
  void release()
})

onMounted(async () => {
  await nextTick()
  // No-op if a signed-in user's own theme (currentUserStore.refresh(), racing
  // this on startup) already applied; see layoutStore's hasUserTheme. A wall
  // display that starts in its remembered screen theme keeps it.
  if (!startsInScreenTheme) initDefaultTheme()
  initEasterEggs()
  // The branding sets the tenant default language for anybody not signed
  // in, which a wall display is, so the screen's language is put back.
  void publicBrandingStore.fetch().then(() => {
    if (startsOnDevice) repaintScreenLanguage()
  })
})
</script>

<template>
  <LiveConnectionHandler />
  <AnnouncementsHandler />
  <ToastHandler />
  <ConfirmHandler />

  <template v-if="firstRouteResolved">
    <AuthLayout v-if="isAuthRoute" />
    <KioskLayout v-else-if="isKioskRoute" />
    <AppLayout v-else />
  </template>
</template>
