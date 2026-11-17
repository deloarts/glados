<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { asyncTab } from '@/shared/utils/asyncTab'
import { useRouteTab } from '@/shared/composables/useRouteTab'
import { useRegisteredAdminSettingsTabs, type AdminSettingsTab } from '@/shared/admin-settings-tabs'

// Platform's own tabs, at the multiples of ten. The tabs of features above
// Platform register themselves (see `@/shared/admin-settings-tabs`) and take
// the order between their neighbours.
const PLATFORM_TABS: AdminSettingsTab[] = [
  {
    value: 'host',
    icon: 'mdi-server-network',
    component: asyncTab(() => import('../components/AdminSettingsTabHost.vue')),
    order: 10,
  },
  {
    value: 'general',
    icon: 'mdi-tune-variant',
    component: asyncTab(() => import('../components/AdminSettingsTabGeneral.vue')),
    order: 20,
  },
  // Right after General: which modules exist shapes everything after it.
  {
    value: 'features',
    icon: 'mdi-toggle-switch-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabFeatures.vue')),
    order: 25,
  },
  {
    value: 'users',
    icon: 'mdi-account-group-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabUsers.vue')),
    order: 30,
  },
  // Off the multiples of ten so the groups sit right after the users they
  // bundle without renumbering every later tab.
  {
    value: 'groups',
    icon: 'mdi-account-multiple-check-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabGroups.vue')),
    order: 35,
  },
  {
    value: 'apiKeys',
    icon: 'mdi-key-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabApiKeys.vue')),
    order: 40,
  },
  {
    value: 'auth',
    icon: 'mdi-account-key-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabAuth.vue')),
    order: 50,
  },
  {
    value: 'mail',
    icon: 'mdi-email-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabMail.vue')),
    order: 60,
  },
  {
    value: 'storage',
    icon: 'mdi-harddisk',
    component: asyncTab(() => import('../components/AdminSettingsTabStorage.vue')),
    order: 70,
  },
  {
    value: 'backups',
    icon: 'mdi-database-arrow-down-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabBackups.vue')),
    order: 80,
  },
  {
    value: 'security',
    icon: 'mdi-shield-lock-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabSecurity.vue')),
    order: 90,
  },
  {
    value: 'numbering',
    icon: 'mdi-pound-box-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabNumbering.vue')),
    order: 110,
  },
  {
    value: 'branding',
    icon: 'mdi-palette-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabBranding.vue')),
    order: 120,
  },
  {
    value: 'notifications',
    icon: 'mdi-bell-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabNotifications.vue')),
    order: 130,
  },
  {
    value: 'solidworks-pdm',
    icon: 'mdi-cube-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabSolidworksPdm.vue')),
    order: 140,
  },
  {
    value: 'data-import',
    icon: 'mdi-table-arrow-left',
    component: asyncTab(() => import('../components/AdminSettingsTabDataImport.vue')),
    order: 150,
  },
  {
    value: 'stock-service',
    icon: 'mdi-package-variant-closed',
    component: asyncTab(() => import('../components/AdminSettingsTabStock.vue')),
    order: 160,
  },
  {
    value: 'aiModels',
    icon: 'mdi-brain',
    component: asyncTab(() => import('../components/AdminSettingsTabAiModels.vue')),
    order: 170,
  },
  {
    value: 'maintenance',
    icon: 'mdi-wrench-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabMaintenance.vue')),
    order: 180,
  },
  {
    value: 'retention',
    icon: 'mdi-database-clock-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabRetention.vue')),
    order: 190,
  },
  {
    value: 'audit',
    icon: 'mdi-history',
    component: asyncTab(() => import('../components/AdminSettingsTabAudit.vue')),
    order: 200,
  },
  {
    value: 'securityLog',
    icon: 'mdi-shield-search',
    component: asyncTab(() => import('../components/AdminSettingsTabSecurityLog.vue')),
    order: 205,
  },
  {
    value: 'logs',
    icon: 'mdi-text-box-search-outline',
    component: asyncTab(() => import('../components/AdminSettingsTabLogs.vue')),
    order: 210,
  },
]

const TABS = [...PLATFORM_TABS, ...useRegisteredAdminSettingsTabs()].sort((a, b) => a.order - b.order)
const VALID_TABS = new Set(TABS.map((tab) => tab.value))

const { t } = useI18n()
const store = useAdminSettingsStore()

const activeTab = useRouteTab({
  param: 'tab',
  validTabs: VALID_TABS,
  defaultTab: 'host',
  basePath: '/settings',
})

onMounted(() => store.fetch())

watchLoadingBar(() => store.loading)
</script>

<template>
  <div class="view-scope">
    <div class="view-content">
      <div class="view-body">
        <Tabs v-model:value="activeTab" class="settings-tabs fill-tabs">
          <TabList>
            <Tab v-for="tab in TABS" :key="tab.value" :value="tab.value">
              <i :class="`mdi ${tab.icon} tab-icon`" aria-hidden="true" />
              {{ t(`adminSettings.tabs.${tab.value}`) }}
            </Tab>
          </TabList>
          <TabPanels>
            <TabPanel v-for="tab in TABS" :key="tab.value" :value="tab.value">
              <component v-if="activeTab === tab.value" :is="tab.component" />
            </TabPanel>
          </TabPanels>
        </Tabs>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.view-scope {
  height: calc(100% + 1rem);
  margin: -0.5rem;
}

.view-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.view-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.settings-tabs {
  flex: 1;
}

.tab-icon {
  margin-right: var(--space-1);
}
</style>
