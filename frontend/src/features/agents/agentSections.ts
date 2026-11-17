import { computed, type Plugin } from 'vue'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import { registerAccountTab } from '@/shared/account-page'
import { registerAdminSettingsTab } from '@/shared/admin-settings-tabs'
import { asyncTab } from '@/shared/utils/asyncTab'

/**
 * Adds the AI agent parts of the Platform pages: the AI Agents tab of the
 * account page, and the agent settings and agent call log tabs of the admin
 * settings. The app shell installs it once with `app.use(agentSections)`,
 * so the account and admin settings pages never import this feature.
 */
export const agentSections: Plugin = {
  install(app) {
    registerAccountTab(app, {
      value: 'ai-agents',
      labelKey: 'agents.tab',
      component: asyncTab(() => import('./views/AccountAgentsView.vue')),
      // After Access Tokens, whose tokens it creates.
      order: 35,
      useAccess() {
        const hostStore = useHostStore()
        const { hasPermission } = usePermissions()
        // Shown while agent access is on, and to everyone who may use an
        // agent, so a consent can always be withdrawn.
        const visible = computed(
          () => hostStore.agentAccessEnabled || hasPermission(Permission.USE_MCP),
        )
        return {
          visible,
          allowed: computed(() => !hostStore.loaded || visible.value),
          icon: computed(() => 'mdi-robot-outline'),
        }
      },
    })

    registerAdminSettingsTab(app, {
      value: 'ai-agents',
      icon: 'mdi-robot-outline',
      component: asyncTab(() => import('./components/AdminSettingsTabAgents.vue')),
      // After AI Models.
      order: 175,
    })

    registerAdminSettingsTab(app, {
      value: 'agent-calls',
      icon: 'mdi-robot-confused-outline',
      component: asyncTab(() => import('./components/AdminSettingsTabAgentCalls.vue')),
      // After the Security Log.
      order: 207,
    })
  },
}
