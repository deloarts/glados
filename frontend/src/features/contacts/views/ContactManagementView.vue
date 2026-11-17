<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import EmptyState from '@/shared/components/EmptyState.vue'
import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { HelpButton } from '@/shared/help'
import ContactFormDialog from '../components/ContactFormDialog.vue'
import ContactManagementTable from '../components/ContactManagementTable.vue'
import { useContactsStore } from '../stores/contactsStore'

import type { MenuItem } from 'openvue/menuitem'

/**
 * The Contacts tab of Resources. Contacts are personal data, so a user
 * without read:contacts sees why the list stays empty instead of it.
 */

const { t } = useI18n()
const store = useContactsStore()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()

const canRead = computed(() => hasPermission(Permission.READ_CONTACTS))
const showCreate = ref(false)

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('contacts.views.sortByItems.nameAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => store.setSort('name', 'asc'),
  },
  {
    label: t('contacts.views.sortByItems.nameDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => store.setSort('name', 'desc'),
  },
  {
    label: t('contacts.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('created', 'desc'),
  },
  {
    label: t('contacts.views.sortByItems.changedDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('changed', 'desc'),
  },
])

const groupByItems = computed<MenuItem[]>(() => [
  {
    label: t('contacts.views.groupByItems.organisation'),
    icon: 'mdi mdi-domain',
    command: () => store.setGroupBy('organisation'),
  },
])

const shellConfig = computed<ManagementCrudShellConfig>(() => ({
  store,
  idPrefix: 'contacts',
  createLabel: t('contacts.createContact'),
  createPermission: Permission.WRITE_CONTACTS,
  sortByItems: sortByItems.value,
  groupByItems: groupByItems.value,
}))

function onCreated(): void {
  store.triggerRefresh()
}
</script>

<template>
  <ManagementCrudShell
    v-if="canRead"
    :config="shellConfig"
    v-model:search="store.search"
    @create="showCreate = true"
  >
    <template #handbook>
      <HelpButton rounded />
    </template>
    <ContactManagementTable />
  </ManagementCrudShell>
  <PageLayout v-else>
    <EmptyState icon="mdi mdi-lock-outline" :message="missing(Permission.READ_CONTACTS)" />
  </PageLayout>

  <ContactFormDialog v-model:visible="showCreate" @saved="onCreated" />
</template>
