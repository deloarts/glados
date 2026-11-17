<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'
import { useAppToast } from '@/core/composables/useAppToast'

import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import { UserManagementTable, UserFormDialog, useUserManagementStore } from '@/features/users'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import type { UserResponse } from '@/core/types/userResponse'

const { t } = useI18n()
const confirm = useConfirm()
const appToast = useAppToast()
const userManagementStore = useUserManagementStore()
const { hasPermission } = usePermissions()

const canManageUsers = computed(() => hasPermission(Permission.WRITE_SETTINGS))

const showCreateForm = ref(false)

// Users have neither a Sort By nor a Group By control today (the columns
// sort individually instead, via the DataTable's own header clicks), and no
// search box, only the per-column filter row. `sortByItems: []` and no
// `v-model:search` binding both reproduce that, the same way an omitted
// `groupByItems` hides the Group By button (see ManagementCrudShellConfig).
const shellConfig = computed<ManagementCrudShellConfig>(() => ({
  store: userManagementStore,
  idPrefix: 'users',
  createLabel: t('settings.users.createUser'),
  createPermission: Permission.WRITE_SETTINGS,
  sortByItems: [],
}))

function onSaved(user: UserResponse): void {
  appToast.success(user.username, t('settings.users.createUser'))
}

function onTerminateAllSessions(): void {
  async function onAccept(): Promise<void> {
    try {
      await userManagementStore.terminateAllSessions()
      appToast.success(t('settings.users.terminateAllSessions'))
    } catch {
      appToast.error(t('settings.users.errors.unknown'))
    }
  }

  confirm.require({
    message: t('settings.users.terminateAllSessionsConfirm'),
    header: t('settings.users.terminateAllSessions'),
    icon: 'mdi mdi-logout-variant',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('settings.users.terminateAllSessions'), severity: 'warn' },
    accept: () => void onAccept(),
  })
}
</script>

<template>
  <ManagementCrudShell :config="shellConfig" @create="showCreateForm = true">
    <template #extra-controls>
      <Button
        :label="t('settings.users.terminateAllSessions')"
        icon="mdi mdi-logout-variant"
        severity="danger"
        text
        :disabled="!canManageUsers"
        @click="onTerminateAllSessions"
      />
    </template>
    <UserManagementTable />
  </ManagementCrudShell>

  <UserFormDialog v-model:visible="showCreateForm" @saved="onSaved" />
</template>
