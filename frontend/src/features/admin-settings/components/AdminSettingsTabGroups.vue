<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import { UserGroupFormDialog, UserGroupManagementTable, useUserGroupsStore } from '@/features/users'
import type { UserGroupResponse } from '@/features/users'
import { useAppToast } from '@/core/composables/useAppToast'
import { Permission } from '@/core/auth/permissions'

const { t } = useI18n()
const toast = useAppToast()
const store = useUserGroupsStore()

const showCreateForm = ref(false)

// Groups are few, so there is a search but no Sort By or Group By.
const shellConfig = computed<ManagementCrudShellConfig>(() => ({
  store,
  idPrefix: 'user-groups',
  createLabel: t('settings.groups.createGroup'),
  createPermission: Permission.WRITE_SETTINGS,
}))

function onSaved(group: UserGroupResponse): void {
  toast.success(group.name, t('settings.groups.created'))
}
</script>

<template>
  <ManagementCrudShell
    :config="shellConfig"
    v-model:search="store.search"
    @create="showCreateForm = true"
  >
    <UserGroupManagementTable />
  </ManagementCrudShell>

  <UserGroupFormDialog v-model:visible="showCreateForm" @saved="onSaved" />
</template>
