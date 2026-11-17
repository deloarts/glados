<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import TokenManagementControls from '@/shared/components/tokens/TokenManagementControls.vue'
import TokenManagementViews from '@/shared/components/tokens/TokenManagementViews.vue'
import TokenManagementTable from '@/shared/components/tokens/TokenManagementTable.vue'
import { HelpButton } from '@/shared/help'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { patsApi } from '../api/patsApi'
import { usePatsStore } from '../stores/patsStore'

const I18N_PREFIX = 'account.pat'

const { t } = useI18n()
const store = usePatsStore()
const userStore = useCurrentUserStore()
const hostStore = useHostStore()

const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()

const isSystem = computed(() => userStore.user?.is_systemuser ?? false)

// Every token on this page is the user's own, and the backend lets an
// owner revoke their own tokens without any permission. Creating one needs
// Write Access Tokens, and the system account never creates one, which the
// page explains in its own message rather than in a tooltip.
const canManage = true
const canCreate = computed(() => !isSystem.value && hasPermission(Permission.WRITE_PAT))
const createBlocked = computed(() => (isSystem.value ? '' : missing(Permission.WRITE_PAT)))
</script>

<template>
  <PageLayout>
    <template #controls>
      <TokenManagementControls
        :store="store"
        :can-manage="canManage"
        :can-create="canCreate"
        :create-blocked="createBlocked"
        :show-create-addin="!isSystem && hostStore.pdmEnabled"
        :show-create-pdm-addin="!isSystem && hostStore.pdmEnabled"
        :i18n-prefix="I18N_PREFIX"
      >
        <template #handbook>
          <HelpButton slug="account/access-tokens" rounded />
        </template>
      </TokenManagementControls>
    </template>
    <template #views>
      <TokenManagementViews :store="store" />
    </template>
    <Message v-if="isSystem" severity="info" :closable="false">
      {{ t('account.pat.systemUserNoCreate') }}
    </Message>
    <TokenManagementTable
      :store="store"
      :api="patsApi"
      :can-manage="canManage"
      :i18n-prefix="I18N_PREFIX"
    />
  </PageLayout>
</template>
