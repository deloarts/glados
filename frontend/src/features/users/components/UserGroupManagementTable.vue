<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'
import { storeToRefs } from 'pinia'

import type { DataTableRowClickEvent, DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import EmptyState from '@/shared/components/EmptyState.vue'
import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePermissions } from '@/core/composables/usePermissions'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { useUsersStore } from '@/core/stores/usersStore'
import { extractApiError } from '@/core/utils/errors'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { permissionLabel, permissionSeverity } from '@/shared/utils/permissionLabels'
import { useUserGroupsStore } from '../stores/userGroupsStore'
import UserGroupFormDialog from './UserGroupFormDialog.vue'

import type { UserGroupResponse } from '../types/userGroup'

const { t } = useI18n()
const confirm = useConfirm()
const toast = useAppToast()
const store = useUserGroupsStore()
const usersStore = useUsersStore()
const { filteredItems, loading, showActions } = storeToRefs(store)
watchLoadingBar(loading)
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const canManage = computed(() => hasPermission(Permission.WRITE_SETTINGS))

const editDialogVisible = ref(false)
const editingGroup = ref<UserGroupResponse | undefined>(undefined)

onMounted(() => {
  void store.refresh()
  void usersStore.ensureLoaded()
})

const MAX_VISIBLE_TAGS = 4

function memberNames(group: UserGroupResponse): string[] {
  return group.member_ids.map((id) => usersStore.getNameById(id))
}

function onEdit(group: UserGroupResponse): void {
  if (!canManage.value) return
  editingGroup.value = group
  editDialogVisible.value = true
}

function onRowClick(event: DataTableRowClickEvent): void {
  onEdit(event.data as UserGroupResponse)
}

function onSaved(group: UserGroupResponse): void {
  toast.success(group.name, t('settings.groups.saved'))
}

function onDelete(group: UserGroupResponse): void {
  async function onAccept(): Promise<void> {
    try {
      await store.remove(group.id)
      toast.success(group.name, t('settings.groups.deleted'))
    } catch (e) {
      toast.error(group.name, extractApiError(e) ?? t('settings.groups.errors.unknown'))
    }
  }

  const names = memberNames(group)
  confirm.require({
    header: t('settings.groups.deleteGroup'),
    message: names.length
      ? t('settings.groups.deleteConfirmMembers', { name: group.name, members: names.join(', ') })
      : t('settings.groups.deleteConfirm', { name: group.name }),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('settings.groups.deleteGroup'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

const cm = ref()
const contextMenuItem = ref<UserGroupResponse | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const group = contextMenuItem.value
  if (!group) return []
  return [
    {
      label: t('settings.groups.editGroup'),
      icon: 'mdi mdi-pencil',
      disabled: !canManage.value,
      command: () => onEdit(group),
    },
    { separator: true },
    {
      label: t('settings.groups.deleteGroup'),
      icon: 'mdi mdi-delete-outline',
      disabled: !canManage.value,
      command: () => onDelete(group),
    },
  ]
})
</script>

<template>
  <DataTable
    :value="filteredItems"
    v-model:context-menu-selection="contextMenuItem"
    data-key="id"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    scrollable
    scroll-height="flex"
    :row-hover="canManage"
    @row-click="onRowClick"
    @row-contextmenu="onRowContextMenu"
  >
    <template #empty>
      <EmptyState />
    </template>

    <Column header="#" body-class="row-number" class="column-fit">
      <template #body="{ index }">{{ index + 1 }}</template>
    </Column>
    <Column v-if="showActions" :header="t('settings.groups.columns.actions')" class="column-fit">
      <template #body="{ data }: { data: UserGroupResponse }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            :disabled="!canManage"
            v-tooltip.top.focus="t('settings.groups.editGroup')"
            :aria-label="t('settings.groups.editGroup')"
            @click.stop="onEdit(data)"
          />
          <Button
            icon="mdi mdi-delete-outline"
            size="small"
            severity="danger"
            text
            :disabled="!canManage"
            v-tooltip.top.focus="t('settings.groups.deleteGroup')"
            :aria-label="t('settings.groups.deleteGroup')"
            @click.stop="onDelete(data)"
          />
        </div>
      </template>
    </Column>
    <Column field="name" :header="t('settings.groups.columns.name')" class="column-fit" />
    <Column field="description" :header="t('settings.groups.columns.description')">
      <template #body="{ data }: { data: UserGroupResponse }">
        <span v-if="data.description">{{ data.description }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('settings.groups.columns.members')">
      <template #body="{ data }: { data: UserGroupResponse }">
        <div v-if="data.member_ids.length" class="tags">
          <Tag
            v-for="name in memberNames(data).slice(0, MAX_VISIBLE_TAGS)"
            :key="name"
            :value="name"
            severity="secondary"
          />
          <Tag
            v-if="data.member_ids.length > MAX_VISIBLE_TAGS"
            v-tooltip.top="memberNames(data).slice(MAX_VISIBLE_TAGS).join(', ')"
            :value="t('settings.groups.more', { count: data.member_ids.length - MAX_VISIBLE_TAGS })"
            severity="secondary"
          />
        </div>
        <span v-else class="text-muted">{{ t('settings.groups.noMembers') }}</span>
      </template>
    </Column>
    <Column :header="t('settings.groups.columns.permissions')">
      <template #body="{ data }: { data: UserGroupResponse }">
        <div v-if="data.permissions.length" class="tags">
          <Tag
            v-for="perm in data.permissions.slice(0, MAX_VISIBLE_TAGS)"
            :key="perm"
            :value="permissionLabel(t, perm)"
            :severity="permissionSeverity(perm)"
          />
          <Tag
            v-if="data.permissions.length > MAX_VISIBLE_TAGS"
            v-tooltip.top="
              data.permissions
                .slice(MAX_VISIBLE_TAGS)
                .map((p) => permissionLabel(t, p))
                .join(', ')
            "
            :value="t('settings.groups.more', { count: data.permissions.length - MAX_VISIBLE_TAGS })"
            severity="secondary"
          />
        </div>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
  </DataTable>

  <ContextMenu ref="cm" :model="contextMenuItems" />
  <UserGroupFormDialog v-model:visible="editDialogVisible" :group="editingGroup" @saved="onSaved" />
</template>

<style scoped lang="scss">
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.text-muted {
  color: var(--p-text-muted-color);
}
</style>
