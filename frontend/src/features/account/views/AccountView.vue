<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Component } from 'vue'

import { usePhoneLayout } from '@/core/composables/usePhoneLayout'
import { asyncTab } from '@/shared/utils/asyncTab'
import { useRouteTab } from '@/shared/composables/useRouteTab'
import { useRegisteredAccountTabs, type AccountTabAccess } from '@/shared/account-page'

interface TabConfig {
  value: string
  labelKey: string
  // A registered tab takes its icon from its access instead.
  icon?: string
  component: Component
  order: number
}

const DEFAULT_TAB = 'me'

// Platform's own tabs, at the multiples of ten. The tabs of features above
// Platform register themselves (see `@/shared/account-page`) and take the
// order between their neighbours.
const PLATFORM_TABS: TabConfig[] = [
  {
    value: 'me',
    labelKey: 'main.sidebar.account.me',
    icon: 'mdi-account',
    component: asyncTab(() => import('./AccountMeView.vue')),
    order: 10,
  },
  {
    value: 'notifications',
    labelKey: 'main.sidebar.account.notifications',
    icon: 'mdi-bell',
    component: asyncTab(() => import('./AccountNotificationsView.vue')),
    order: 20,
  },
  {
    value: 'pat',
    labelKey: 'main.sidebar.account.pat',
    icon: 'mdi-key',
    component: asyncTab(() => import('./AccountAccessTokenView.vue')),
    order: 30,
  },
  {
    value: '2fa',
    labelKey: 'main.sidebar.account.twoFactor',
    icon: 'mdi-shield-key',
    component: asyncTab(() => import('@/features/auth/views/TwoFactorView.vue')),
    order: 40,
  },
  {
    value: 'passkeys',
    labelKey: 'main.sidebar.account.passkeys',
    icon: 'mdi-fingerprint',
    component: asyncTab(() => import('@/features/auth/views/PasskeysView.vue')),
    order: 50,
  },
  {
    value: 'sessions',
    labelKey: 'main.sidebar.account.sessions',
    icon: 'mdi-monitor-lock',
    component: asyncTab(() => import('./AccountSessionsView.vue')),
    order: 60,
  },
  {
    value: 'permissions',
    labelKey: 'main.sidebar.account.permissions',
    icon: 'mdi-shield-check',
    component: asyncTab(() => import('./AccountPermissionsView.vue')),
    order: 70,
  },
]

const { t } = useI18n()

// Each registered tab decides for itself whether it applies to the signed-in
// user and which icon it shows.
const registeredTabs = useRegisteredAccountTabs().map((tab) => ({ tab, access: tab.useAccess() }))
const accessByTab = new Map<string, AccountTabAccess>(
  registeredTabs.map(({ tab, access }) => [tab.value, access]),
)

const TABS: TabConfig[] = [...PLATFORM_TABS, ...registeredTabs.map(({ tab }) => tab)].sort(
  (a, b) => a.order - b.order,
)
const VALID_TABS = new Set(TABS.map((tab) => tab.value))

const { tabOffered } = usePhoneLayout()
const visibleTabs = computed(() =>
  TABS.filter(
    (tab) => (accessByTab.get(tab.value)?.visible.value ?? true) && tabOffered(tab.value),
  ),
)

function tabIcon(tab: TabConfig): string {
  return accessByTab.get(tab.value)?.icon.value ?? tab.icon ?? ''
}

function isAllowed(tab: string): boolean {
  return accessByTab.get(tab)?.allowed.value ?? true
}

const activeTab = useRouteTab({
  param: 'tab',
  validTabs: VALID_TABS,
  defaultTab: DEFAULT_TAB,
  basePath: '/account',
  isAllowed,
})

watch(
  () => isAllowed(activeTab.value),
  (allowed) => {
    if (!allowed) activeTab.value = DEFAULT_TAB
  },
)
</script>

<template>
  <div class="section-view">
    <Tabs v-model:value="activeTab" class="section-tabs fill-tabs">
      <TabList>
        <Tab v-for="tab in visibleTabs" :key="tab.value" :value="tab.value">
          <i :class="`mdi ${tabIcon(tab)} tab-icon`" aria-hidden="true" />
          {{ t(tab.labelKey) }}
        </Tab>
      </TabList>
      <TabPanels>
        <TabPanel v-for="tab in visibleTabs" :key="tab.value" :value="tab.value">
          <component v-if="activeTab === tab.value" :is="tab.component" />
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped lang="scss">
.section-view {
  height: calc(100% + 1rem);
  margin: -0.5rem;
}

.section-tabs {
  height: 100%;
}

.tab-icon {
  margin-right: var(--space-1);
}
</style>
