<script setup lang="ts">
import { onMounted, ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'
import { useAppToast } from '@/core/composables/useAppToast'
import { storeToRefs } from 'pinia'
import {
  formatISODate as formatDate,
  formatISODateTime as formatDateTime,
} from '@/core/utils/dates'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useServerTable } from '@/core/composables/useServerTable'

import type { DataTableRowContextMenuEvent, DataTableSortEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { useUsersStore } from '@/core/stores/usersStore'
import { useUserManagementStore } from '../stores/userManagementStore'
import { useUserGroupsStore } from '../stores/userGroupsStore'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'
import UserFormDialog from './UserFormDialog.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePermissions } from '@/core/composables/usePermissions'
import { useClipboard } from '@/core/composables/useClipboard'
import { Permission } from '@/core/auth/permissions'
import type { UserResponse } from '@/core/types/userResponse'
import type { UserSortBy } from '@/core/types/userRequest'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { permissionLabel as formatPermissionLabel, permissionSeverity } from '@/shared/utils/permissionLabels'

const { t } = useI18n()
const confirm = useConfirm()
const toast = useAppToast()
const { copyToClipboard } = useClipboard()

const usersStore = useUsersStore()
const managementStore = useUserManagementStore()
const groupsStore = useUserGroupsStore()
const { tableItems, loading, filters, clearTrigger, sortBy, sortDir } = storeToRefs(managementStore)
watchLoadingBar(loading)
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const canManageUsers = computed(() => hasPermission(Permission.WRITE_SETTINGS))

const editDialogVisible = ref(false)
const editingUser = ref<UserResponse | undefined>(undefined)

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: ({ first, rows }) => ({ skip: first, limit: rows }),
  fetch: (params) => managementStore.refreshTable(params),
})

watch(filters, resetAndFetchDebounced, { deep: true })

watch(clearTrigger, () => {
  resetAndFetch()
})

watch([sortBy, sortDir], () => {
  resetAndFetch()
})

watch(
  () => managementStore.refreshTrigger,
  () => fetchItems(),
)

// The members column resolves names from the picker-facing users list,
// which the table fetch does not fill.
onMounted(() => {
  void usersStore.ensureLoaded()
  void groupsStore.ensureLoaded()
})

function groupNames(ids: number[]): string[] {
  return ids.map((id) => groupsStore.getById(id)?.name).filter((n): n is string => !!n)
}

const activeOptions = [
  { label: t('settings.users.filters.active'), value: true },
  { label: t('settings.users.filters.inactive'), value: false },
]

function onEditUser(user: UserResponse): void {
  editingUser.value = user
  editDialogVisible.value = true
}

function onSaved(user: UserResponse): void {
  toast.success(user.username, t('settings.users.editUser'))
}

function onTerminateSession(user: UserResponse): void {
  async function onAccept(): Promise<void> {
    try {
      await managementStore.terminateSession(user.id)
      toast.success(user.username, t('settings.users.terminateSession'))
    } catch {
      toast.error(t('settings.users.errors.unknown'))
    }
  }

  confirm.require({
    message: t('settings.users.terminateSessionConfirm', { name: user.username }),
    header: t('settings.users.terminateSession'),
    icon: 'mdi mdi-logout-variant',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('settings.users.terminateSession'), severity: 'warn' },
    accept: () => void onAccept(),
  })
}

function permissionLabel(perm: string): string {
  return formatPermissionLabel(t, perm)
}

const MAX_VISIBLE_PERMISSIONS = 4

function visiblePermissions(perms: string[] | null | undefined): string[] {
  return (perms ?? []).slice(0, MAX_VISIBLE_PERMISSIONS)
}

function hiddenPermissions(perms: string[] | null | undefined): string[] {
  return (perms ?? []).slice(MAX_VISIBLE_PERMISSIONS)
}

const MAX_VISIBLE_MEMBERS = 3

function memberNames(ids: number[]): string[] {
  return ids.map((id) => usersStore.getNameById(id))
}

function visibleMembers(ids: number[]): string[] {
  return memberNames(ids).slice(0, MAX_VISIBLE_MEMBERS)
}

function hiddenMembers(ids: number[]): string[] {
  return memberNames(ids).slice(MAX_VISIBLE_MEMBERS)
}

const cm = ref()
const contextMenuItem = ref<UserResponse | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

// Server-side sort. The controlled sortField and sortOrder keep the header
// icon in step with the view's sort control.
function onSort(event: DataTableSortEvent): void {
  if (typeof event.sortField === 'string' && event.sortOrder) {
    managementStore.setSort(event.sortField as UserSortBy, event.sortOrder === 1 ? 'asc' : 'desc')
  } else {
    managementStore.clearSort()
  }
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const user = contextMenuItem.value
  if (!user) return []

  // Lets a row be edited without enabling the hidden actions column.
  return [
    {
      label: t('settings.users.editUser'),
      icon: 'mdi mdi-pencil',
      disabled: !canManageUsers.value,
      command: () => onEditUser(user),
    },
    {
      label: t('settings.users.terminateSession'),
      icon: 'mdi mdi-logout-variant',
      disabled: !canManageUsers.value || !user.last_logged_in,
      command: () => onTerminateSession(user),
    },
    { separator: true },
    {
      label: t('common.copyUuid'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(user.public_id),
    },
  ]
})
</script>

<template>
  <DataTable
    :value="tableItems"
    v-model:filters="filters"
    v-model:context-menu-selection="contextMenuItem"
    filter-display="row"
    data-key="id"
    lazy
    paginator
    :total-records="managementStore.total"
    :first="first"
    :rows="rows"
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    @page="onPage"
    :sort-field="sortBy ?? undefined"
    :sort-order="sortBy ? (sortDir === 'asc' ? 1 : -1) : undefined"
    removable-sort
    @sort="onSort"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    scrollable
    scroll-height="flex"
    resizable-columns
    column-resize-mode="fit"
    class="users-table"
    @row-contextmenu="onRowContextMenu"
  >
    <template #empty>
      <EmptyState />
    </template>

    <Column
      v-if="managementStore.showActions"
      :header="t('settings.users.columns.actions')"
      style="width: 6rem"
    >
      <template #body="{ data }: { data: UserResponse }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            :disabled="!canManageUsers"
            v-tooltip.top.focus="t('settings.users.editUser')"
            :aria-label="t('settings.users.editUser')"
            @click="onEditUser(data)"
          />
          <Button
            icon="mdi mdi-logout-variant"
            size="small"
            severity="warn"
            text
            :disabled="!canManageUsers || !data.last_logged_in"
            v-tooltip.top.focus="t('settings.users.terminateSession')"
            :aria-label="t('settings.users.terminateSession')"
            @click="onTerminateSession(data)"
          />
        </div>
      </template>
    </Column>
    <Column
      field="username"
      :header="t('settings.users.columns.username')"
      :show-filter-menu="false"
      sortable
    >
      <template #body="{ data }: { data: UserResponse }">
        <div class="username-cell">
          <UserAvatarPreview :user="data" :show-name="false" />
          <Tag v-if="data.is_systemuser" :value="data.username.toUpperCase()" severity="warn" />
          <span v-else>{{ data.username }}</span>
        </div>
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('settings.users.filters.username')"
          :aria-label="t('common.filterBy', { column: t('settings.users.columns.username') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      field="full_name"
      :header="t('settings.users.columns.fullName')"
      :show-filter-menu="false"
      sortable
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('settings.users.filters.fullName')"
          :aria-label="t('common.filterBy', { column: t('settings.users.columns.fullName') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      field="email"
      :header="t('settings.users.columns.email')"
      :show-filter-menu="false"
      sortable
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('settings.users.filters.email')"
          :aria-label="t('common.filterBy', { column: t('settings.users.columns.email') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      field="is_active"
      :header="t('settings.users.columns.active')"
      :show-filter-menu="false"
      style="width: 9rem"
    >
      <template #body="{ data }: { data: UserResponse }">
        <Tag
          :value="
            data.is_active
              ? t('settings.users.filters.active')
              : t('settings.users.filters.inactive')
          "
          :severity="data.is_active ? 'success' : 'danger'"
        />
      </template>
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="activeOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('settings.users.filters.allActive')"
          :aria-label="t('common.filterBy', { column: t('settings.users.columns.active') })"
          show-clear
          size="small"
          fluid
          @change="filterCallback()"
        />
      </template>
    </Column>
    <Column field="totp_enabled" header="2FA" style="width: 8rem">
      <template #body="{ data }: { data: UserResponse }">
        <Tag
          :value="data.totp_enabled ? 'TOTP' : t('common.disabled')"
          :severity="data.totp_enabled ? 'success' : 'secondary'"
        />
      </template>
    </Column>
    <Column
      field="auth_provider"
      :header="t('settings.users.columns.authProvider')"
      style="width: 9rem"
    >
      <template #body="{ data }: { data: UserResponse }">
        <Tag
          :value="t(`settings.users.authProviders.${data.auth_provider}`)"
          :severity="data.auth_provider === 'ldap' ? 'info' : 'secondary'"
        />
      </template>
    </Column>
    <Column :header="t('settings.users.columns.permissions')">
      <template #body="{ data }: { data: UserResponse }">
        <div v-if="data.is_systemuser" class="permissions-tags">
          <Tag :value="permissionLabel('fullControl')" :severity="permissionSeverity('danger')" />
        </div>
        <div v-else class="permissions-tags">
          <Tag
            v-for="perm in visiblePermissions(data.permissions)"
            :key="perm"
            :value="permissionLabel(perm)"
            :severity="permissionSeverity(perm)"
          />
          <Tag
            v-if="hiddenPermissions(data.permissions).length"
            v-tooltip.top="hiddenPermissions(data.permissions).map(permissionLabel).join(', ')"
            :value="
              t('settings.users.morePermissions', {
                count: hiddenPermissions(data.permissions).length,
              })
            "
            severity="secondary"
          />
        </div>
      </template>
    </Column>
    <Column :header="t('settings.users.columns.groups')">
      <template #body="{ data }: { data: UserResponse }">
        <div v-if="data.group_ids.length" class="permissions-tags">
          <Tag v-for="name in groupNames(data.group_ids)" :key="name" :value="name" severity="secondary" />
        </div>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('settings.users.columns.members')">
      <template #body="{ data }: { data: UserResponse }">
        <div v-if="data.is_shared_account" class="permissions-tags">
          <Tag
            v-for="name in visibleMembers(data.member_ids)"
            :key="name"
            :value="name"
            severity="secondary"
          />
          <Tag
            v-if="hiddenMembers(data.member_ids).length"
            v-tooltip.top="hiddenMembers(data.member_ids).join(', ')"
            :value="
              t('settings.users.moreMembers', { count: hiddenMembers(data.member_ids).length })
            "
            severity="secondary"
          />
          <span v-if="!data.member_ids.length" class="text-muted">
            {{ t('settings.users.columns.noMembers') }}
          </span>
        </div>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column
      field="created"
      :header="t('settings.users.columns.created')"
      sortable
      style="width: 8rem"
    >
      <template #body="{ data }: { data: UserResponse }">
        {{ formatDate(data.created) }}
      </template>
    </Column>
    <Column :header="t('settings.users.columns.lastLoggedIn')" style="width: 10rem">
      <template #body="{ data }: { data: UserResponse }">
        <span v-if="data.last_logged_in">{{ formatDateTime(data.last_logged_in) }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column field="language" :header="t('settings.users.columns.language')" style="width: 8rem">
      <template #body="{ data }: { data: UserResponse }">
        <Tag :value="data.language" />
      </template>
    </Column>
    <Column field="theme_preset" :header="t('settings.users.columns.theme')" style="width: 10rem">
      <template #body="{ data }: { data: UserResponse }">
        {{ data.theme_preset }} / {{ data.theme_primary }} / {{ data.theme_surface }} /
        {{ data.theme_dark_mode ? 'dark' : 'light' }}
      </template>
    </Column>
    <Column style="width: 100%" />
  </DataTable>

  <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />

  <UserFormDialog v-model:visible="editDialogVisible" :user="editingUser" @saved="onSaved" />
</template>

<style scoped lang="scss">
.users-table {
  width: 100%;
}

.permissions-tags {
  display: flex;
  gap: var(--space-1);
}

.username-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
