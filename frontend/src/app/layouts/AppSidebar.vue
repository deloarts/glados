<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { updateUser } from '@/core/api/users/updateUser'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { localeEndonym } from '@/core/i18n/localeMessages'
import { useProductionPlanning } from '@/core/composables/useProductionPlanning'
import { usePhoneLayout } from '@/core/composables/usePhoneLayout'
import { useAppToast } from '@/core/composables/useAppToast'
import { useClockIcon } from '@/shared/composables/useClockIcon'
import { useTimeTrackingAccountStore, useTimeTrackingAvailability } from '@/features/time-tracking'
import type { Schemas } from '@/core/api/generated'

const layoutStore = useLayoutStore()

const { isDarkMode, isSidebarWide } = storeToRefs(layoutStore)

const { toggleDarkMode, toggleSidebarWide } = layoutStore

// On a phone the sidebar is an overlay with room to spare and no hover for
// tooltips, so it always shows its labels, and it lists only the sections a
// phone offers. The width toggle has nothing to switch there.
const { isPhone } = usePhoneLayout()
const showLabels = computed(() => isSidebarWide.value || isPhone.value)
const { locale, t } = useI18n()
const appToast = useAppToast()

const route = useRoute()

const userStore = useCurrentUserStore()
const hostStore = useHostStore()
const { productionPlanningEnabled } = useProductionPlanning()

// The Time Tracking shortcut shows once the stored credentials are usable.
// That is Glados state, so loading it on sign-in never contacts the time
// tracking system; a changed password surfaces on the first Time Tracking
// load, which marks the credentials and hides the shortcut again.
const timeTrackingStore = useTimeTrackingAccountStore()
const { available: timeTrackingAvailable } = useTimeTrackingAvailability()
const clockIcon = useClockIcon()
const showTimeTracking = computed(
  () => timeTrackingAvailable.value && timeTrackingStore.credentialsValid,
)

watch(
  timeTrackingAvailable,
  (available) => {
    if (available) void timeTrackingStore.ensureLoaded()
  },
  { immediate: true },
)

const langPopover = ref()

const LANG_META: Record<string, { label: string; flag: string }> = {
  enGB: { label: localeEndonym('enGB'), flag: '🇬🇧' },
  deAT: { label: localeEndonym('deAT'), flag: '🇦🇹' },
}

// The sidebar names the active language as the language menu does, by its
// own name, instead of printing the locale code.
const currentLanguageLabel = computed(() => LANG_META[locale.value]?.label ?? locale.value)

const languages = computed(() =>
  hostStore.languages.map((code) => ({
    code,
    ...(LANG_META[code] ?? { label: code, flag: '🌐' }),
  })),
)

interface Props {
  collapsed: boolean
}

defineProps<Props>()
defineEmits<{ (e: 'update:collapsed', v: boolean): void }>()

const isAdmin = computed(() => userStore.isAdmin)

function isActive(to: string) {
  return route.path.startsWith(to)
}

function navTooltip(label: string) {
  return showLabels.value ? undefined : label
}

function openLangPopover(event: Event) {
  langPopover.value.toggle(event)
}

async function setLocale(code: string) {
  locale.value = code
  langPopover.value.hide()
  const userId = userStore.user?.id
  if (userId === undefined) return

  try {
    // The picker only ever offers codes from the server's own /host/values
    // list, always a subset of this closed wire vocabulary; hostStore
    // itself keeps that list as plain strings (out of scope here), so the
    // selected value is cast at this boundary rather than threading a
    // narrower type through it.
    await updateUser(userId, { language: code as Schemas['Language'] })
  } catch {
    appToast.error(t('main.sidebar.errors.preferenceSaveFailed'))
  }
}

async function onToggleDarkMode() {
  const newValue = toggleDarkMode()
  const userId = userStore.user?.id
  if (userId === undefined) return

  try {
    await updateUser(userId, { theme_dark_mode: newValue })
  } catch {
    appToast.error(t('main.sidebar.errors.preferenceSaveFailed'))
  }
}
</script>

<template>
  <nav class="sidebar" :class="{ wide: showLabels }" v-if="!collapsed">
    <!-- NAVIGATION: scrolls on its own once the rail runs out of height -->
    <div class="nav-scroll">
      <!-- OVERVIEW -->
      <div class="nav-group">
        <router-link
          class="nav-item"
          :class="{ active: isActive('/dashboard') }"
          to="/dashboard"
          :aria-label="t('main.sidebar.dashboard.label')"
          data-testid="nav-dashboard"
          v-tooltip.right="navTooltip(t('main.sidebar.dashboard.label'))"
        >
          <i class="mdi mdi-view-dashboard" aria-hidden="true" />
          <span v-if="showLabels" class="nav-label">{{
            t('main.sidebar.dashboard.label')
          }}</span>
        </router-link>

        <router-link
          v-if="hostStore.todosEnabled"
          class="nav-item"
          :class="{ active: isActive('/todo') }"
          to="/todo"
          :aria-label="t('main.sidebar.todo.label')"
          data-testid="nav-todo"
          v-tooltip.right="navTooltip(t('main.sidebar.todo.label'))"
        >
          <i class="mdi mdi-checkbox-marked-outline" aria-hidden="true" />
          <span v-if="showLabels" class="nav-label">{{ t('main.sidebar.todo.label') }}</span>
        </router-link>

        <router-link
          v-if="showTimeTracking"
          class="nav-item"
          :class="{ active: isActive('/account/time-tracking') }"
          to="/account/time-tracking"
          :aria-label="t('main.sidebar.timeTracking.label')"
          data-testid="nav-time-tracking"
          v-tooltip.right="navTooltip(t('main.sidebar.timeTracking.label'))"
        >
          <i :class="`mdi ${clockIcon}`" aria-hidden="true" />
          <span v-if="showLabels" class="nav-label">{{
            t('main.sidebar.timeTracking.label')
          }}</span>
        </router-link>
      </div>

      <div class="nav-divider" />

      <!-- WORK -->
      <div class="nav-group">
        <router-link
          class="nav-item"
          :class="{ active: isActive('/workspace') }"
          to="/workspace"
          :aria-label="t('main.sidebar.workspace.label')"
          data-testid="nav-workspace"
          v-tooltip.right="navTooltip(t('main.sidebar.workspace.label'))"
        >
          <i class="mdi mdi-folder" aria-hidden="true" />
          <span v-if="showLabels" class="nav-label">{{
            t('main.sidebar.workspace.label')
          }}</span>
        </router-link>

        <router-link
          class="nav-item"
          :class="{ active: isActive('/catalogue') }"
          to="/catalogue/bought-items"
          :aria-label="t('main.sidebar.catalogue.label')"
          data-testid="nav-catalogue"
          v-tooltip.right="navTooltip(t('main.sidebar.catalogue.label'))"
        >
          <i class="mdi mdi-book-open-page-variant" aria-hidden="true" />
          <span v-if="showLabels" class="nav-label">{{
            t('main.sidebar.catalogue.label')
          }}</span>
        </router-link>

        <router-link
          class="nav-item"
          :class="{ active: isActive('/procurement') }"
          to="/procurement/orders"
          :aria-label="t('main.sidebar.procurement.label')"
          data-testid="nav-procurement"
          v-tooltip.right="navTooltip(t('main.sidebar.procurement.label'))"
        >
          <i class="mdi mdi-cart" aria-hidden="true" />
          <span v-if="showLabels" class="nav-label">{{
            t('main.sidebar.procurement.label')
          }}</span>
        </router-link>

        <router-link
          v-if="productionPlanningEnabled"
          class="nav-item"
          :class="{ active: isActive('/production') }"
          to="/production/lots"
          :aria-label="t('main.sidebar.production.label')"
          data-testid="nav-production"
          v-tooltip.right="navTooltip(t('main.sidebar.production.label'))"
        >
          <i class="mdi mdi-factory" aria-hidden="true" />
          <span v-if="showLabels" class="nav-label">{{
            t('main.sidebar.production.label')
          }}</span>
        </router-link>
      </div>

      <div class="nav-divider" />

      <!-- TABLES AND TOOLS -->
      <div class="nav-group">
        <router-link
          class="nav-item"
          :class="{ active: isActive('/tables') }"
          to="/tables"
          :aria-label="t('main.sidebar.tables.label')"
          data-testid="nav-tables"
          v-tooltip.right="navTooltip(t('main.sidebar.tables.label'))"
        >
          <i class="mdi mdi-table-large" aria-hidden="true" />
          <span v-if="showLabels" class="nav-label">{{ t('main.sidebar.tables.label') }}</span>
        </router-link>

        <router-link
          v-if="!isPhone"
          class="nav-item"
          :class="{ active: isActive('/tools') }"
          to="/tools"
          :aria-label="t('main.sidebar.tools.label')"
          data-testid="nav-tools"
          v-tooltip.right="navTooltip(t('main.sidebar.tools.label'))"
        >
          <i class="mdi mdi-toolbox" aria-hidden="true" />
          <span v-if="showLabels" class="nav-label">{{ t('main.sidebar.tools.label') }}</span>
        </router-link>
      </div>

      <div class="nav-divider" />

      <!-- RESOURCES -->
      <div class="nav-group">
        <router-link
          class="nav-item"
          :class="{ active: isActive('/resources') }"
          to="/resources"
          :aria-label="t('main.sidebar.resources.label')"
          data-testid="nav-resources"
          v-tooltip.right="navTooltip(t('main.sidebar.resources.label'))"
        >
          <i class="mdi mdi-bookshelf" aria-hidden="true" />
          <span v-if="showLabels" class="nav-label">{{
            t('main.sidebar.resources.label')
          }}</span>
        </router-link>
      </div>
    </div>

    <div class="nav-divider" />

    <!-- PREFERENCES -->
    <div class="nav-group">
      <div
        class="nav-item"
        role="button"
        tabindex="0"
        :aria-label="t('main.sidebar.languageSelect.label') + ': ' + currentLanguageLabel"
        @click="openLangPopover"
        @keydown.enter="openLangPopover"
        @keydown.space.prevent="openLangPopover"
        v-tooltip.right="
          navTooltip(t('main.sidebar.languageSelect.label') + ': ' + currentLanguageLabel)
        "
      >
        <i class="mdi mdi-web" aria-hidden="true" />
        <span v-if="showLabels" class="nav-label">
          {{ t('main.sidebar.languageSelect.label') }}: {{ currentLanguageLabel }}
        </span>
      </div>

      <Popover ref="langPopover">
        <div class="lang-list">
          <button
            v-for="lang in languages"
            :key="lang.code"
            class="lang-item"
            :class="{ active: locale === lang.code }"
            @click="setLocale(lang.code)"
          >
            <span class="lang-flag">{{ lang.flag }}</span>
            <span class="lang-label">{{ lang.label }}</span>
            <i v-if="locale === lang.code" class="mdi mdi-check lang-check" aria-hidden="true" />
          </button>
        </div>
      </Popover>

      <div
        class="nav-item"
        role="button"
        tabindex="0"
        data-testid="dark-mode-toggle"
        :aria-label="t('main.sidebar.modeSwitch.label')"
        @click="onToggleDarkMode"
        @keydown.enter="onToggleDarkMode"
        @keydown.space.prevent="onToggleDarkMode"
        v-tooltip.right="navTooltip(t('main.sidebar.modeSwitch.label'))"
      >
        <i
          :class="isDarkMode ? 'mdi mdi-weather-night' : 'mdi mdi-weather-sunny'"
          aria-hidden="true"
        />
        <span v-if="showLabels" class="nav-label">{{ t('main.sidebar.modeSwitch.label') }}</span>
      </div>

      <div
        v-if="!isPhone"
        class="nav-item"
        role="button"
        tabindex="0"
        :aria-label="t('main.sidebar.toggleSidebar.label')"
        @click="toggleSidebarWide"
        @keydown.enter="toggleSidebarWide"
        @keydown.space.prevent="toggleSidebarWide"
        v-tooltip.right="navTooltip(t('main.sidebar.toggleSidebar.label'))"
      >
        <i
          :class="isSidebarWide ? 'mdi mdi-arrow-collapse-left' : 'mdi mdi-arrow-expand-right'"
          aria-hidden="true"
        />
        <span v-if="showLabels" class="nav-label">{{
          t('main.sidebar.toggleSidebar.label')
        }}</span>
      </div>
    </div>

    <!-- SETTINGS -->
    <template v-if="isAdmin && !isPhone">
      <div class="nav-divider" />

      <div class="nav-group">
        <router-link
          class="nav-item"
          :class="{ active: isActive('/settings') }"
          to="/settings"
          :aria-label="t('main.sidebar.settings.label')"
          data-testid="nav-settings"
          v-tooltip.right="navTooltip(t('main.sidebar.settings.label'))"
        >
          <i class="mdi mdi-tune" aria-hidden="true" />
          <span v-if="showLabels" class="nav-label">{{ t('main.sidebar.settings.label') }}</span>
        </router-link>
      </div>
    </template>
  </nav>
</template>

<style scoped lang="scss">
.sidebar {
  display: flex;
  user-select: none;
  flex-direction: column;

  height: 100%;
  width: 100%;

  border-right: 1px solid var(--p-content-border-color);

  overflow: hidden;
}

.nav-group {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

// Takes the free height and pushes the preferences and settings to the bottom
// of the rail. On a viewport too short for every entry only this region
// scrolls, so the preferences, the rail toggle and the settings stay
// reachable. Tooltips and the language popover are teleported to the body, so
// the scroll container never clips them.
.nav-scroll {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;

  overflow-x: hidden;
  overflow-y: auto;
}

.nav-divider {
  flex-shrink: 0;
  border-top: 1px solid var(--p-content-border-color);
}

.nav-item {
  position: relative;

  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);

  height: 3.2rem;
  width: 100%;
  padding: 0 var(--space-4);

  cursor: pointer;

  color: var(--p-surface-800);
  border-left: 0.3rem solid transparent;
  border-right: 0.3rem solid transparent;
}

.sidebar.wide .nav-item {
  justify-content: flex-start;
}

// A laptop at 125 % scaling leaves too little height for every entry at full
// size, so short viewports get compact rows and only really short ones need
// the navigation to scroll.
@media (max-height: $bp-height-compact) {
  .nav-item {
    height: 2.6rem;
  }
}

.nav-item i {
  font-size: var(--font-size-xl);
  flex-shrink: 0;
  // The icon sits on top of .nav-item's own click/keydown handlers (or, for
  // router-link items, its native anchor navigation); without this, a
  // pointer/automation click landing on the glyph itself doesn't reliably
  // reach the wrapping element.
  pointer-events: none;
}

.nav-item:focus-visible {
  outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
  outline-offset: -2px;
}

// The label inherits the item's colour, so dark mode lightens the item
// itself; lightening only the icon left the label dark on dark.
.p-dark .nav-item {
  color: var(--p-surface-200);
}

.nav-label {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: var(--font-size-sm);
}

.nav-item:hover {
  background-color: var(--p-surface-100);
}

.p-dark .nav-item:hover {
  background-color: var(--p-surface-800);
}

.nav-item:hover i {
  color: var(--p-surface-950);
}

.p-dark .nav-item:hover i {
  color: var(--p-surface-0);
}

.nav-item.active {
  color: var(--p-surface-950);
  background-color: var(--p-surface-100);
  border-left-color: var(--p-primary-500);
}

.p-dark .nav-item.active {
  color: var(--p-surface-100);
  background-color: var(--p-surface-800);
  border-left-color: var(--p-primary-500);
}

.nav-item::before {
  content: '';
  position: absolute;
  inset: 0;
}

.sidebar.collapsed .nav-item {
  justify-content: center;
}

.lang-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 10rem;
  padding: var(--space-1) 0;
}

.lang-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: none;
  border-radius: var(--p-content-border-radius);
  background: transparent;
  cursor: pointer;
  color: var(--p-text-color);
  font-size: var(--font-size-sm);
  text-align: left;
  transition: background 0.15s;
}

.lang-item:hover {
  background: var(--p-surface-100);
}

.p-dark .lang-item:hover {
  background: var(--p-surface-800);
}

.lang-item.active {
  font-weight: 600;
}

.lang-flag {
  font-size: var(--font-size-lg);
  line-height: 1;
}

.lang-label {
  flex: 1;
}

.lang-check {
  font-size: var(--font-size-xs);
  color: var(--p-primary-color);
}
</style>
