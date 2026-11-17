<script setup lang="ts">
import { defineAsyncComponent, h, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'
import AppFooter from './AppFooter.vue'
import AppBottomNav from './AppBottomNav.vue'
import MaintenanceBanner from './MaintenanceBanner.vue'
import AnnouncementBanner from './AnnouncementBanner.vue'
import VersionMismatchBanner from './VersionMismatchBanner.vue'
import SystemUserWarningDialog from './SystemUserWarningDialog.vue'
import { AcknowledgementDialog } from '@/features/announcements'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { usePageTitle } from '@/core/composables/usePageTitle'
import { usePhoneLayout } from '@/core/composables/usePhoneLayout'
// Imported directly rather than through the production barrel: the barrel
// re-exports dialogs that pull in most other features, and the bundler keeps
// every re-exported SFC, so the barrel import alone would put ~600 kB of feature
// code into the entry chunk.
import { useLotDetail } from '@/shared/composables/useLotDetail'
import { useScan } from '@/features/scan'
import AsyncChunkLoading from '@/shared/components/layout/AsyncChunkLoading.vue'
import DesktopOnlyNotice from '@/shared/components/layout/DesktopOnlyNotice.vue'

// AppLayout is reached statically from App.vue for every signed-in user, so
// a static import here would drag LotDetailContent (the largest component
// in the app) into the initial bundle for users who never open Production.
const LotDetailDialog = defineAsyncComponent({
  loader: () => import('@/features/production/lots/components/LotDetailDialog.vue'),
  // Overlay, not in-flow: this renders as a direct child of `.app-shell`,
  // which is a column flex container, so an in-flow placeholder becomes a
  // fourth flex item and pushes the footer up off the bottom of the screen
  // until the chunk lands.
  loadingComponent: () => h(AsyncChunkLoading, { overlay: true }),
  delay: 200,
})

// Same reasoning as LotDetailDialog above: ScanDialog pulls in qr-scanner
// (~544K), so a static import here would ship it to every signed-in user
// even if they never open the scanner.
const ScanDialog = defineAsyncComponent({
  loader: () => import('@/features/scan/components/ScanDialog.vue'),
  loadingComponent: () => h(AsyncChunkLoading, { overlay: true }),
  delay: 200,
})

// An expanded rail would take 44 of a phone's 390 pixels before any content
// begins, so on a phone it starts collapsed and opens as an overlay from the
// bottom navigation instead (see the media query below), and crossing the
// breakpoint re-applies the default for the width you land on. The overlay
// closes again once you navigate, since it covers the page you picked.
const phoneLayout = usePhoneLayout()
const { isPhone, phoneMode, showDesktopNotice } = phoneLayout
const route = useRoute()
const sidebarCollapsed = ref(isPhone.value)
watch(isPhone, (phone) => {
  sidebarCollapsed.value = phone
})
watch(
  () => route.fullPath,
  () => {
    if (isPhone.value) sidebarCollapsed.value = true
  },
)

const { isSidebarWide } = storeToRefs(useLayoutStore())
const lotDetail = useLotDetail()
const scan = useScan()
const { t } = useI18n()

// Installed once here rather than in every view: AppLayout is the shell for
// every authenticated route (App.vue mounts AuthLayout instead for /login),
// so this alone keeps document.title current for the whole signed-in app.
usePageTitle()
</script>

<template>
  <div
    class="app-shell"
    :class="{
      'sidebar-collapsed': sidebarCollapsed,
      'sidebar-wide': isSidebarWide || isPhone,
    }"
  >
    <a class="skip-link" href="#main-content">{{ t('common.skipToContent') }}</a>

    <VersionMismatchBanner />
    <AnnouncementBanner />

    <header class="shell-header">
      <AppHeader />
    </header>

    <MaintenanceBanner />

    <div class="shell-body">
      <aside class="shell-sidebar">
        <AppSidebar v-model:collapsed="sidebarCollapsed" />
      </aside>

      <!-- A tap target only, out of the tab order: the More button closes the
           overlay from the keyboard. -->
      <button
        v-if="isPhone && !sidebarCollapsed"
        type="button"
        class="shell-backdrop"
        tabindex="-1"
        :aria-label="t('main.sidebar.toggleSidebar.label')"
        @click="sidebarCollapsed = true"
      />

      <main
        id="main-content"
        class="shell-main"
        :class="{ 'phone-mode': phoneMode }"
        tabindex="-1"
      >
        <DesktopOnlyNotice
          v-if="showDesktopNotice"
          @show-anyway="phoneLayout.showDesktopAnyway()"
        />
        <RouterView v-else />
      </main>
    </div>

    <div v-if="isPhone" class="shell-bottom-nav">
      <AppBottomNav v-model:sidebar-collapsed="sidebarCollapsed" />
    </div>
    <footer v-else class="shell-footer">
      <AppFooter />
    </footer>

    <LotDetailDialog v-model:visible="lotDetail.visible.value" :lot-id="lotDetail.lotId.value" />
    <ScanDialog v-model:visible="scan.visible.value" />
    <SystemUserWarningDialog />
    <AcknowledgementDialog />
  </div>
</template>

<style scoped lang="scss">
.app-shell {
  --sidebar-w: var(--sidebar-width);
  &.sidebar-wide {
    --sidebar-w: var(--sidebar-width-wide);
  }
  &.sidebar-collapsed {
    --sidebar-w: 0px;
  }

  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Skip link ──────────────────────────────────────────────────────────── */
/* Visually hidden until it receives keyboard focus: a mouse user never sees
   it, but it is the first tab stop for anyone navigating by keyboard, letting
   them jump straight past the header and sidebar into the page content. */
.skip-link {
  position: absolute;
  top: -3rem;
  left: 0.5rem;
  z-index: 1000;
  padding: var(--space-2) var(--space-4);
  background: var(--p-primary-500);
  color: var(--on-accent);
  border-radius: var(--p-border-radius-sm);
  transition: top 0.15s ease;

  &:focus-visible {
    top: 0.5rem;
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: 2px;
  }
}

/* ── Header / Footer ────────────────────────────────────────────────────── */
.shell-header {
  flex: 0 0 var(--header-height);
  z-index: 10;
}

.shell-footer {
  flex: 0 0 var(--footer-height);
  z-index: 10;
}

/* The bottom navigation takes the footer's place on a phone, and grows by
   the home indicator's inset once the app is installed full screen. */
.shell-bottom-nav {
  flex: 0 0 calc(var(--bottom-nav-height) + env(safe-area-inset-bottom, 0px));
  z-index: 10;
}

/* ── Body ───────────────────────────────────────────────────────────────── */
.shell-body {
  flex: 1;
  min-height: 0;
  /*
   * Containing block for .shell-sidebar: the sidebar spans exactly this
   * element, whatever sits above it (AnnouncementBanner, MaintenanceBanner)
   * or below it (footer). No overflow:hidden here, the sidebar must be able
   * to overflow.
   */
  position: relative;
}

/* ── Sidebar ────────────────────────────────────────────────────────────── */
.shell-sidebar {
  /*
   * Anchored to .shell-body rather than the viewport, because a fixed
   * sidebar below var(--header-height) assumes the header starts at y:0.
   * Every banner rendered above the header (AnnouncementBanner) or between
   * header and body (MaintenanceBanner) pushes .shell-body down, and a
   * viewport-anchored sidebar would then overlap the header or banner.
   * .app-shell is itself fixed to the viewport, so absolute-in-body behaves
   * exactly like fixed placement when no banner is shown.
   */
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: var(--sidebar-w);

  /*
   * The sidebar handles a short viewport itself by scrolling its navigation
   * region, so this column never needs a scrollbar of its own.
   */
  overflow: visible;
  z-index: 100;
  transition: width 0.2s ease;
}

/* ── Main ───────────────────────────────────────────────────────────────── */
.shell-main {
  height: 100%;
  max-height: 100%;
  padding: var(--space-2);
  margin-left: var(--sidebar-w);

  overflow-y: auto;
  overflow-x: hidden;
  transition: margin-left 0.2s ease;

  background-color: var(--p-surface-100);
}

.p-dark .shell-main {
  background-color: var(--p-surface-900);
}

/* ── Small screens ──────────────────────────────────────────────────────── */
/*
 * The rail becomes an overlay rather than a column: --sidebar-w drives the
 * main pane's margin, so pinning it to 0 lets content use the full width while
 * the sidebar element keeps its own width and floats above. Opening the rail on
 * a phone then covers content instead of squeezing it into an unusable strip.
 */
@media (max-width: $bp-sm) {
  .app-shell,
  .app-shell.sidebar-wide,
  .app-shell.sidebar-collapsed {
    --sidebar-w: 0px;
  }

  .shell-sidebar {
    width: var(--sidebar-width);
    background-color: var(--p-content-background);
    box-shadow: var(--shadow-side);
  }

  .app-shell.sidebar-wide .shell-sidebar {
    width: var(--sidebar-width-wide);
  }

  .app-shell.sidebar-collapsed .shell-sidebar {
    width: 0;
    box-shadow: none;
  }

  /* Dims the page under the open overlay, and a tap on it closes the overlay. */
  .shell-backdrop {
    position: absolute;
    inset: 0;
    z-index: 99;
    padding: 0;
    border: none;
    background-color: var(--p-mask-background);
  }
}
</style>
