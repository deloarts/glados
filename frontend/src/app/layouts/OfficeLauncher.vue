<script setup lang="ts">
/**
 * The "waffle": a 3x3 grid button at the far left of the header that opens
 * a popover of quick-links to the Microsoft 365 web apps (Outlook, Teams,
 * Word, Excel, PowerPoint, OneDrive, SharePoint), mirroring the launcher
 * every M365 web app itself shows in its own top-left corner. Link-out only:
 * no SSO, no Graph API, no document embedding.
 *
 * Gated behind hostStore.officeLauncherEnabled (an admin setting, off by
 * default); renders nothing when it's off. Deliberately does NOT call
 * hostStore.fetch() itself: the router guard already populates the store on
 * every authenticated navigation, and AppHeader.spec.ts mounts AppHeader
 * against a fresh pinia with no host-API mock, relying on nothing here
 * triggering a network call.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useHostStore } from '@/core/host/stores/hostStore'
import { isSafeHttpUrl } from '@/shared/utils/isSafeHttpUrl'

const { t } = useI18n()
const hostStore = useHostStore()

const popover = ref()
const isOpen = ref(false)

function toggle(event: Event): void {
  popover.value?.toggle(event)
}

interface OfficeTile {
  key: string
  label: string
  href: string
  icon: string
  color: string
}

// Tenant-agnostic M365 web-app URLs (verified live 2026-08-24): they
// route on the signed-in account, so none of these need admin
// configuration, unlike SharePoint below.
const CORE_TILES: ReadonlyArray<Omit<OfficeTile, 'label'>> = [
  {
    key: 'outlook',
    href: 'https://outlook.cloud.microsoft/',
    icon: 'mdi-microsoft-outlook',
    color: '#0078D4',
  },
  {
    key: 'teams',
    href: 'https://teams.cloud.microsoft/',
    icon: 'mdi-microsoft-teams',
    color: '#5059C9',
  },
  {
    key: 'word',
    href: 'https://word.cloud.microsoft/',
    icon: 'mdi-microsoft-word',
    color: '#185ABD',
  },
  {
    key: 'excel',
    href: 'https://excel.cloud.microsoft/',
    icon: 'mdi-microsoft-excel',
    color: '#107C41',
  },
  {
    key: 'powerpoint',
    href: 'https://powerpoint.cloud.microsoft/',
    icon: 'mdi-microsoft-powerpoint',
    color: '#C43E1C',
  },
  {
    key: 'oneDrive',
    href: 'https://onedrive.cloud.microsoft/',
    icon: 'mdi-microsoft-onedrive',
    color: '#0364B8',
  },
]

// The stored URL is admin-supplied and lands directly in an href. The
// backend validates the scheme on save too, but Vue does not sanitise
// `:href`, so a corrupted value must never resolve to a javascript: or
// data: scheme here either.
const sharePointTile = computed<OfficeTile | null>(() => {
  const url = hostStore.officeSharepointUrl
  if (!isSafeHttpUrl(url)) return null
  return {
    key: 'sharePoint',
    href: url,
    icon: 'mdi-microsoft-sharepoint',
    color: '#038387',
    label: t('officeLauncher.sharePoint'),
  }
})

const tiles = computed<OfficeTile[]>(() => {
  const base = CORE_TILES.map((tile) => ({ ...tile, label: t(`officeLauncher.${tile.key}`) }))
  return sharePointTile.value ? [...base, sharePointTile.value] : base
})
</script>

<template>
  <template v-if="hostStore.officeLauncherEnabled">
    <!-- Sized and positioned to exactly match .shell-sidebar's icon column
         (same var(--sidebar-width), same flush-left x:0 origin via the
         negative margin below), so the waffle lines up vertically with the
         sidebar's nav-item icons directly beneath it regardless of either
         side's own padding. -->
    <div class="office-launcher-slot">
      <Button
        class="office-launcher-trigger"
        aria-haspopup="dialog"
        :aria-expanded="isOpen"
        v-tooltip.bottom="t('officeLauncher.title')"
        :aria-label="t('officeLauncher.title')"
        @click="toggle"
      >
        <svg
          class="waffle-glyph"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
          focusable="false"
        >
          <rect x="0.5" y="0.5" width="5" height="5" rx="1.1" />
          <rect x="7.5" y="0.5" width="5" height="5" rx="1.1" />
          <rect x="14.5" y="0.5" width="5" height="5" rx="1.1" />
          <rect x="0.5" y="7.5" width="5" height="5" rx="1.1" />
          <rect x="7.5" y="7.5" width="5" height="5" rx="1.1" />
          <rect x="14.5" y="7.5" width="5" height="5" rx="1.1" />
          <rect x="0.5" y="14.5" width="5" height="5" rx="1.1" />
          <rect x="7.5" y="14.5" width="5" height="5" rx="1.1" />
          <rect x="14.5" y="14.5" width="5" height="5" rx="1.1" />
        </svg>
      </Button>
    </div>

    <Popover
      ref="popover"
      class="office-launcher-popover"
      @show="isOpen = true"
      @hide="isOpen = false"
    >
      <div class="office-launcher-menu">
        <a
          class="office-launcher-header"
          href="https://m365.cloud.microsoft/"
          target="_blank"
          rel="noopener noreferrer"
        >
          <span>{{ t('officeLauncher.microsoft365') }}</span>
          <i class="mdi mdi-arrow-top-right" aria-hidden="true" />
        </a>

        <div class="office-launcher-grid">
          <a
            v-for="tile in tiles"
            :key="tile.key"
            class="office-launcher-tile"
            :href="tile.href"
            target="_blank"
            rel="noopener noreferrer"
          >
            <span class="tile-icon" :style="{ backgroundColor: tile.color }">
              <i class="mdi" :class="tile.icon" aria-hidden="true" />
            </span>
            <span class="tile-label">{{ tile.label }}</span>
          </a>
        </div>
      </div>
    </Popover>
  </template>
</template>

<style scoped lang="scss">
// Centers the trigger inside a column exactly var(--sidebar-width) wide,
// flush against x:0 (the negative margin cancels .header's own 1rem left
// padding); the same box .shell-sidebar and its centered .nav-item icons
// occupy, so the waffle lines up vertically with the sidebar's icon column
// beneath it. Sharing the CSS var (rather than a hand-measured offset) keeps
// the two in sync if the sidebar's width ever changes.
.office-launcher-slot {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: var(--sidebar-width);
  margin-left: -1rem;
}

// Copied verbatim from AppHeader.vue's .header-button rules (see the class
// comment above sanitizeMailHtml import): this component's template has two
// root-level siblings (Button + Popover), so Vue never forwards AppHeader's
// scope id here and `.header-button[data-v-x]` would never match. Without
// this own copy, the trigger renders as an unstyled default-primary Button,
// invisible against the header's primary-500 background.
.office-launcher-trigger {
  color: var(--header-fg);
  background-color: transparent;
  border: 1px solid transparent;
  border-radius: 50%;
}

.office-launcher-trigger:hover {
  background-color: var(--p-primary-600);
  border: 1px solid transparent;
}

.p-dark .office-launcher-trigger:hover {
  color: var(--header-fg);
  background-color: var(--p-primary-600);
  border: 1px solid transparent;
}

// Hidden on a phone: .header-left has no min-width:0 on any child and is
// already tight against the brand logo/wordmark at small widths, so another
// control would overflow. Native Office apps
// cover the same use case there. Hides the whole slot, not just the button,
// so no empty var(--sidebar-width) gap is left behind.
@media (max-width: $bp-sm) {
  .office-launcher-slot {
    display: none;
  }
}

.waffle-glyph {
  width: 1.15rem;
  height: 1.15rem;
  display: block;
}

.office-launcher-menu {
  display: flex;
  flex-direction: column;
  min-width: 16rem;
}

.office-launcher-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);

  padding: var(--space-3) var(--space-4);

  font-weight: 600;
  font-size: var(--font-size-sm);
  color: var(--p-text-color);
  text-decoration: none;

  border-bottom: 1px solid var(--p-content-border-color);
}

.office-launcher-header:hover {
  background: var(--p-surface-100);
}

.p-dark .office-launcher-header:hover {
  background: var(--p-surface-800);
}

.office-launcher-header i {
  font-size: var(--font-size-md);
  color: var(--p-text-muted-color);
}

.office-launcher-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-1);
  padding: var(--space-3);
}

.office-launcher-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);

  padding: var(--space-2) var(--space-1);

  color: var(--p-text-color);
  text-decoration: none;
  border-radius: var(--p-content-border-radius);
}

.office-launcher-tile:hover {
  background: var(--p-surface-100);
}

.p-dark .office-launcher-tile:hover {
  background: var(--p-surface-800);
}

// Fixed brand-coloured square behind a white glyph, deliberately not a
// tinted icon on a transparent background: against Aura's dark content
// surface several products (Word, OneDrive, Teams) drop under the 3:1
// non-text contrast minimum when tinted. A fixed coloured tile keeps
// contrast identical in both light and dark mode.
.tile-icon {
  display: flex;
  align-items: center;
  justify-content: center;

  width: 2rem;
  height: 2rem;

  color: var(--on-accent);
  border-radius: var(--p-content-border-radius);
}

.tile-icon .mdi {
  font-size: var(--font-size-lg);
}

.tile-label {
  overflow: hidden;
  max-width: 100%;

  font-size: var(--font-size-xs);
  text-align: center;
  white-space: nowrap;
  text-overflow: ellipsis;
}
</style>

<!-- OpenVue teleports the popover to <body>, outside this component's
     scope-id ancestry, so its own .p-popover wrapper is unreachable from the
     scoped block above (even via :deep()); same pattern as AppHeader.vue's
     .user-drawer block. Only the padding needs overriding here; the header
     row and tile grid manage their own via the scoped classes above, which
     DO reach the popover's slot content. -->
<style lang="scss">
.office-launcher-popover {
  --p-popover-content-padding: 0;
}
</style>
