<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import UserAvatar from '@/shared/components/user/UserAvatar.vue'
import OfficeLauncher from './OfficeLauncher.vue'
import { APERTURE_BRAND, useEasterEggs } from '@/core/composables/useEasterEggs'
import { rollTestSubject, testSubjectName } from '@/core/utils/testSubject'
import { NotificationPanel, useNotificationsStore } from '@/features/notifications'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import { useLoadingBarStore } from '@/core/stores/loadingBarStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useActivityHeartbeat } from '@/core/composables/useActivityHeartbeat'
import { useSessionCountdown } from '@/core/composables/useSessionCountdown'
import { useScan } from '@/features/scan'

const { t } = useI18n()
const router = useRouter()
const publicBrandingStore = usePublicBrandingStore()
const loadingBarStore = useLoadingBarStore()
const userStore = useCurrentUserStore()
const countdown = useSessionCountdown()
const { apertureMode } = useEasterEggs()

// The tagline follows the same rule as the logo: Aperture mode owns the
// brand slot outright, so nothing from the tenant's branding shows there.
const showDescription = computed(
  () => !apertureMode.value && publicBrandingStore.appDescription !== null,
)

const notificationsStore = useNotificationsStore()

onMounted(() => notificationsStore.startPolling())
useActivityHeartbeat()
onUnmounted(() => notificationsStore.stopPolling())

const userDrawerVisible = ref(false)
const currentUser = computed(() => userStore.user)

// Rolled per opening and deliberately not persisted: the reveal lasts exactly
// as long as that one look at the drawer, so closing and reopening gives you
// your own name back and leaves you unsure you saw it. Aperture mode shows it
// unconditionally and never consumes the monthly allowance.
const revealTestSubject = ref(false)

watch(userDrawerVisible, (open) => {
  revealTestSubject.value = open ? rollTestSubject() : false
})

const identityName = computed(() => {
  const user = currentUser.value
  if (!user) return ''
  if (apertureMode.value || revealTestSubject.value) return testSubjectName(user.id)
  return user.full_name
})

const scan = useScan()
const searchQuery = ref('')
const searchInput = ref<{ $el: HTMLInputElement } | null>(null)

function onSearchSubmit() {
  const q = searchQuery.value.trim()
  if (q) void router.push({ name: 'Search', query: { q } })
}

function clearSearch() {
  searchQuery.value = ''
  searchInput.value?.$el.focus()
}

function goToAccount() {
  userDrawerVisible.value = false
  void router.push('/account/me')
}

// A notification that links to a record, such as a meeting, closes the
// drawer and opens it.
function openNotification(path: string) {
  userDrawerVisible.value = false
  void router.push(path)
}

function logout() {
  userDrawerVisible.value = false
  userStore.logout()
}
</script>

<template>
  <div class="header">
    <ProgressBar v-if="loadingBarStore.isLoading" mode="indeterminate" class="global-loading-bar" />
    <div class="header-left">
      <OfficeLauncher />

      <!-- Aperture mode forces the wordmark: the dot-matrix face is the whole
           point of the egg, and a logo-branded deployment would never show it. -->
      <div class="brand-block" :class="{ 'has-description': showDescription }">
        <img
          v-if="publicBrandingStore.logoUrl && !apertureMode"
          :src="publicBrandingStore.logoUrl"
          class="brand-logo"
          :alt="publicBrandingStore.appName"
        />
        <span v-else class="brand">{{
          apertureMode ? APERTURE_BRAND : publicBrandingStore.appName
        }}</span>
        <span v-if="showDescription" class="brand-description">{{
          publicBrandingStore.appDescription
        }}</span>
      </div>
    </div>
    <div class="header-center">
      <IconField class="header-search">
        <InputIcon class="mdi mdi-magnify" />
        <InputText
          ref="searchInput"
          v-model="searchQuery"
          :placeholder="t('common.search')"
          @keyup.enter="onSearchSubmit"
          @keyup.esc="clearSearch"
        />
        <InputIcon
          v-if="searchQuery"
          class="mdi mdi-close search-clear"
          role="button"
          tabindex="0"
          :aria-label="t('common.clear')"
          v-tooltip.bottom="t('common.clear')"
          @click="clearSearch"
          @keyup.enter="clearSearch"
        />
      </IconField>
      <Button
        v-if="scan.cameraAvailable.value"
        class="header-button header-scan"
        icon="mdi mdi-qrcode-scan"
        v-tooltip.bottom.focus="t('scan.title')"
        :aria-label="t('scan.title')"
        @click="scan.openScan()"
      />
    </div>
    <div class="header-right">
      <Button
        class="header-button"
        icon="mdi mdi-book-open-variant"
        v-tooltip.bottom="t('handbook.title')"
        :aria-label="t('handbook.title')"
        @click="router.push('/handbook')"
      />
      <OverlayBadge
        :value="
          notificationsStore.unreadCount > 0 ? String(notificationsStore.unreadCount) : undefined
        "
        class="overlay-badge"
        :pt="{ pcBadge: { root: { class: 'header-badge' } } }"
      >
        <Button
          class="header-button avatar-button"
          v-tooltip.bottom="t('main.sidebar.account.label')"
          :aria-label="t('main.sidebar.account.label')"
          @click="userDrawerVisible = true"
        >
          <UserAvatar
            v-if="currentUser"
            :user-id="currentUser.id"
            :has-avatar="currentUser.has_avatar"
            img-class="avatar-thumb"
          >
            <i class="mdi mdi-account" aria-hidden="true" />
          </UserAvatar>
          <i v-else class="mdi mdi-account" aria-hidden="true" />
        </Button>
      </OverlayBadge>
      <span
        v-if="countdown.isActive.value"
        class="session-countdown"
        :class="{ warning: countdown.isWarning.value }"
        role="timer"
        aria-live="off"
        v-tooltip.bottom="t('main.header.sessionCountdown.tooltip')"
        >{{ countdown.label }}</span
      >
    </div>
  </div>

  <Drawer
    v-model:visible="userDrawerVisible"
    position="right"
    class="user-drawer sized-drawer"
    :pt="{ content: { class: 'user-drawer-content' } }"
  >
    <template #header>
      <div class="drawer-identity">
        <div class="identity-avatar">
          <UserAvatar
            v-if="currentUser"
            :user-id="currentUser.id"
            :has-avatar="currentUser.has_avatar"
            img-class="identity-avatar-img"
          >
            <i class="mdi mdi-account" aria-hidden="true" />
          </UserAvatar>
          <i v-else class="mdi mdi-account" aria-hidden="true" />
        </div>
        <div class="identity-text">
          <span class="identity-name">{{ identityName }}</span>
          <span class="identity-mail">{{ currentUser?.email }}</span>
        </div>
      </div>
    </template>

    <div class="drawer-body">
      <Button
        :label="t('main.sidebar.account.viewAccount')"
        icon="mdi mdi-account-circle"
        variant="outlined"
        class="drawer-action"
        @click="goToAccount"
      />

      <Divider />

      <div class="drawer-notifications">
        <NotificationPanel
          :items="notificationsStore.notifications"
          :loading="notificationsStore.loading"
          @mark-read="notificationsStore.markRead($event)"
          @mark-all-read="notificationsStore.markAllRead()"
          @open="openNotification"
        />
      </div>

      <Divider />

      <Button
        :label="t('main.sidebar.logout.label')"
        icon="mdi mdi-logout"
        severity="danger"
        variant="outlined"
        class="drawer-action"
        @click="logout"
      />
    </div>
  </Drawer>
</template>

<style scoped lang="scss">
.header {
  position: relative;

  display: flex;
  align-items: center;
  justify-content: space-between;

  height: var(--header-height);

  padding: 0 var(--space-2) 0 var(--space-4);

  // --header-fg, not --p-primary-contrast-color: the contrast colour turns
  // dark under .p-dark and flashed the wordmark and icons black on a reload.
  color: var(--header-fg);
  background-color: var(--p-primary-500);
  user-select: none;
}

.global-loading-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.header-center {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  flex: 1;
  min-width: 0;
}

.header-search {
  width: 100%;
  max-width: 24rem;
  --p-iconfield-icon-color: var(--on-accent-soft);
}

// Unlike --p-surface-*, OpenVue's --p-primary-* scale is not redefined
// under .p-dark (verified: identical values in both modes for this Aura
// preset), and .header's own primary-500 background does not change either,
// so this needs no separate dark-mode override to stay correct.
.header-search :deep(input) {
  width: 100%;
  background-color: var(--p-primary-700);
  border: 1px solid var(--p-primary-400);
  color: var(--header-fg);

  &::placeholder {
    color: var(--on-accent-muted);
  }

  // OpenVue's hover swaps in its own grey border, which reads as black on
  // the primary bar, so the border and text are pinned here as well.
  &:hover {
    color: var(--header-fg);
    background-color: var(--p-primary-800);
    border-color: var(--p-primary-400);
  }

  &:focus {
    background-color: var(--p-primary-700);
    border-color: var(--header-fg);
  }
}

// An InputIcon is a plain span, so it gets no pointer affordance of its own.
.header-search :deep(.search-clear) {
  cursor: pointer;
  pointer-events: auto;

  &:hover,
  &:focus-visible {
    color: var(--header-fg);
  }
}

// Scanning matters most on mobile, so the scan button (the other child of
// .header-center) must stay visible, only the text input collapses.
// A phone searches from the search page and scans from the bottom
// navigation, which also opens the sidebar.
@media (max-width: $bp-sm) {
  .header-search,
  .header-scan {
    display: none;
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.header-button {
  color: var(--header-fg);
  background-color: transparent;
  border: 1px solid transparent;
  border-radius: 50%;
}

// :not(:disabled) matches the specificity of OpenVue's own button hover rule,
// whose colour is the theme's contrast colour and would turn the icon dark.
.header-button:not(:disabled):hover {
  color: var(--header-fg);
  background-color: var(--p-primary-600);
  border: 1px solid transparent;
}

.session-countdown {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-2);
  margin-left: var(--space-1);

  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
  color: var(--header-fg);

  background-color: var(--on-accent-hover);
  border-radius: 999px;
}

// Like --p-primary-* above, --p-red-* is a primitive palette OpenVue does
// not redefine under .p-dark (the other header-adjacent use of it, AppFooter's
// .is-offline, needs no dark override either), so this stays readable on
// .header's primary-500 background in both modes without one.
.session-countdown.warning {
  background-color: var(--p-red-600);
}

// Keeps the badge from being clipped by the header edge.
.overlay-badge {
  margin-right: var(--space-2);
}

.avatar-button {
  padding: var(--space-1);
}

.avatar-button :deep(.avatar-thumb) {
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  object-fit: cover;
  display: block;
}

.avatar-button .mdi {
  font-size: var(--font-size-xl);
  line-height: 1.75rem;
}

.drawer-identity {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.identity-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.75rem;
  height: 2.75rem;
  flex-shrink: 0;
  border-radius: 50%;
  background-color: var(--p-surface-200);
  color: var(--p-text-muted-color);
  overflow: hidden;
}

.p-dark .identity-avatar {
  background-color: var(--p-surface-700);
}

.identity-avatar .mdi {
  font-size: var(--font-size-2xl);
}

.identity-avatar :deep(.identity-avatar-img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.identity-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.identity-name {
  font-weight: 600;
  font-size: var(--font-size-md);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.identity-mail {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.drawer-body {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.drawer-action {
  width: 100%;
  flex-shrink: 0;
}

// Takes the leftover space so the trailing divider and logout stay at the bottom.
.drawer-notifications {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  display: flex;
}

.overlay-badge :deep(.header-badge) {
  border: none;
  box-shadow: none;
  outline: none;
  background-color: var(--p-badge-danger-background);
  color: var(--p-badge-danger-color);
  min-width: 1.1rem;
  height: 1.1rem;
  font-size: var(--font-size-xs);
  line-height: 1.1rem;
}

.overlay-badge :deep(.header-badge:empty) {
  display: none;
}

.brand {
  font-family: var(--font-brand);
  font-size: var(--font-brand-size);

  color: var(--header-fg);

  letter-spacing: 1px;
  line-height: 1;
}

.brand-logo {
  max-height: calc(var(--header-height) - 1rem);
  max-width: 10rem;
  object-fit: contain;
  display: block;
}

.brand-block {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  min-width: 0;
}

// Wordmark (28px, line-height 1) plus this row has to fit the fixed
// 3.5rem header, hence the tight line-height and the single-line clamp.
.brand-description {
  color: var(--header-fg);
  opacity: 0.85;

  font-size: var(--font-size-xs);
  line-height: 1.1;
  letter-spacing: 0.02em;
  white-space: nowrap;

  max-width: 14rem;
  margin-top: var(--space-1);
  overflow: hidden;
  text-overflow: ellipsis;
}

// A logo already eats most of the header; give some of it back when a
// tagline sits underneath so the two never overflow the bar.
.has-description .brand-logo {
  max-height: calc(var(--header-height) - 1.75rem);
}
</style>

<!-- The drawer is teleported to the body, so its internals need unscoped rules. -->
<style lang="scss">
.user-drawer {
  --drawer-width: 28rem;
  --p-divider-horizontal-margin: var(--space-3) 0;
}

.user-drawer .user-drawer-content {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding-bottom: var(--space-4);
}
</style>
