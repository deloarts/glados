<script setup lang="ts">
/**
 * The contacts of a project on its overview: its product's, inherited,
 * which the project can mute for itself, and its own, which it can unlink.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { ContactLinksSection } from '@/features/contacts'
import type { ContactLinksApi, LinkedContactRow } from '@/features/contacts'
import { LiveResource } from '@/core/realtime/resources'
import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import type { LiveSignal } from '@/core/realtime/types'
import {
  getProjectContacts,
  linkProjectContact,
  setProjectContactMeetingNotes,
  unlinkProjectContact,
} from '../api/projectContactsApi'
import type { ProjectContactResponse } from '../api/projectContactsApi'
import type { ProjectResponse } from '../types/projectResponse'

const props = defineProps<{
  project: ProjectResponse
}>()

const { t } = useI18n()
const { hasPermission } = usePermissions()
const currentUserStore = useCurrentUserStore()
const { missing } = useMissingPermission()

// Linking follows the project's own edit rights: a manager, or its designated user with write rights.
const canWrite = computed(
  () =>
    hasPermission(Permission.MANAGE_PROJECTS) ||
    (hasPermission(Permission.WRITE_PROJECTS) &&
      props.project.designated_user_id === currentUserStore.user?.id),
)
const writeBlocked = computed(() => {
  if (canWrite.value) return ''
  if (!hasPermission(Permission.WRITE_PROJECTS)) return missing(Permission.WRITE_PROJECTS)
  return t('resources.projects.detail.editDesignatedOnly')
})

const api = computed<ContactLinksApi<ProjectContactResponse>>(() => {
  const id = props.project.id
  return {
    list: () => getProjectContacts(id),
    link: (contactId, receives) => linkProjectContact(id, contactId, receives),
    setMeetingNotes: (contactId, receives) => setProjectContactMeetingNotes(id, contactId, receives),
    unlink: (contactId) => unlinkProjectContact(id, contactId),
  }
})

const productNumber = computed(() => props.project.product?.product_number ?? null)

function toRow(entry: ProjectContactResponse): LinkedContactRow {
  return {
    contact: entry.contact,
    receivesMeetingNotes: entry.receives_meeting_notes,
    sourceLabel: entry.inherited
      ? productNumber.value
        ? t('contacts.links.fromProduct', { number: productNumber.value })
        : t('contacts.links.fromProductUnnamed')
      : null,
    sourceHint: entry.inherited ? t('contacts.links.inheritedHint') : null,
    canUnlink: !entry.inherited,
  }
}

// The project lists its product's links too, so a change there concerns it.
function concernsProject(signal: LiveSignal): boolean {
  if (signal.resource === LiveResource.PROJECT_CONTACTS) return signal.id === props.project.id
  if (signal.resource === LiveResource.PRODUCT_CONTACTS) return signal.id === props.project.product_id
  return true
}

const customerName = computed(
  () => props.project.customer?.name ?? props.project.product?.customer?.name ?? null,
)
</script>

<template>
  <ContactLinksSection
    :owner-key="`project-${project.id}-${project.product_id ?? 'none'}`"
    :hint="t('contacts.links.projectHint')"
    :api="api"
    :to-row="toRow"
    :customer-id="project.customer_id ?? project.product?.customer_id ?? null"
    :customer-name="customerName"
    show-source
    :can-write="canWrite"
    :write-blocked="writeBlocked"
    :live-resources="[LiveResource.PROJECT_CONTACTS, LiveResource.PRODUCT_CONTACTS, LiveResource.CONTACTS]"
    :live-filter="concernsProject"
  />
</template>
