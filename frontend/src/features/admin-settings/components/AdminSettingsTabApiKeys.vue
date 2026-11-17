<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import TokenManagementControls from '@/shared/components/tokens/TokenManagementControls.vue'
import TokenManagementViews from '@/shared/components/tokens/TokenManagementViews.vue'
import TokenManagementTable from '@/shared/components/tokens/TokenManagementTable.vue'
import { HelpButton } from '@/shared/help'
import ApiKeyDocsPanel from './ApiKeyDocsPanel.vue'
import TerminalKeyDialog from './TerminalKeyDialog.vue'
import { usePermissions } from '@/core/composables/usePermissions'
import { useUsersStore } from '@/core/stores/usersStore'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { apiKeysApi } from '../api/apiKeysApi'
import { useApiKeysStore } from '../stores/apiKeysStore'

const I18N_PREFIX = 'settings.apiKeys'

const { t } = useI18n()
const store = useApiKeysStore()
const usersStore = useUsersStore()
const { hasPermission } = usePermissions()

const canManage = computed(() => hasPermission(Permission.MANAGE_API_KEYS))
const { missing } = useMissingPermission()

const showDocs = ref(false)
const showTerminalKey = ref(false)

onMounted(() => {
  void usersStore.refresh()
})
</script>

<template>
  <PageLayout :data-class="showDocs ? 'api-keys-view-data' : undefined">
    <template #controls>
      <TokenManagementControls
        :store="store"
        :can-manage="canManage"
        :create-blocked="missing(Permission.MANAGE_API_KEYS)"
        :manage-blocked="missing(Permission.MANAGE_API_KEYS)"
        :i18n-prefix="I18N_PREFIX"
      >
        <template #start-extra>
          <span v-tooltip.bottom="missing(Permission.MANAGE_API_KEYS) || undefined">
            <Button
              :label="t('settings.apiKeys.terminalKey.button')"
              icon="mdi mdi-monitor-dashboard"
              severity="contrast"
              text
              :disabled="!canManage"
              data-testid="create-terminal-key"
              @click="showTerminalKey = true"
            />
          </span>
        </template>
        <template #handbook>
          <HelpButton rounded />
        </template>
      </TokenManagementControls>
    </template>
    <template #views>
      <TokenManagementViews :store="store">
        <template #start-extra>
          <Button
            :label="t('settings.apiKeys.docs.toggle')"
            icon="mdi mdi-api"
            severity="contrast"
            :text="!showDocs"
            @click="showDocs = !showDocs"
          />
        </template>
      </TokenManagementViews>
    </template>

    <template v-if="showDocs" #panels-end>
      <ApiKeyDocsPanel @close="showDocs = false" />
    </template>

    <TokenManagementTable
      :store="store"
      :api="apiKeysApi"
      :can-manage="canManage"
      :manage-blocked="missing(Permission.MANAGE_API_KEYS)"
      :i18n-prefix="I18N_PREFIX"
      :resolve-creator-name="usersStore.getNameById"
    />
  </PageLayout>

  <TerminalKeyDialog v-model:visible="showTerminalKey" @created="store.triggerRefresh()" />
</template>

<style scoped lang="scss">
:deep(.api-keys-view-data) {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: var(--space-2);

  > .card {
    flex: 1;
    min-width: 0;
    overflow-y: auto;
  }
}
</style>
