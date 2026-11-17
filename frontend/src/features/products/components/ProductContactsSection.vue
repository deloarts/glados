<script setup lang="ts">
/**
 * The contacts of a product on its overview, which every project of the
 * product inherits.
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
  getProductContacts,
  linkProductContact,
  setProductContactMeetingNotes,
  unlinkProductContact,
} from '../api/productContactsApi'
import type { ProductContactResponse } from '../api/productContactsApi'
import type { ProductResponse } from '../types/productResponse'

const props = defineProps<{
  product: ProductResponse
}>()

const { t } = useI18n()
const { hasPermission } = usePermissions()
const currentUserStore = useCurrentUserStore()
const { missing } = useMissingPermission()

// Linking follows the product's own edit rights: a manager, or its designated user with write rights.
const canWrite = computed(
  () =>
    hasPermission(Permission.MANAGE_PROJECTS) ||
    (hasPermission(Permission.WRITE_PROJECTS) &&
      props.product.designated_user_id === currentUserStore.user?.id),
)
const writeBlocked = computed(() => {
  if (canWrite.value) return ''
  if (!hasPermission(Permission.WRITE_PROJECTS)) return missing(Permission.WRITE_PROJECTS)
  return t('resources.products.detail.editDesignatedOnly')
})

const api = computed<ContactLinksApi<ProductContactResponse>>(() => {
  const id = props.product.id
  return {
    list: () => getProductContacts(id),
    link: (contactId, receives) => linkProductContact(id, contactId, receives),
    setMeetingNotes: (contactId, receives) => setProductContactMeetingNotes(id, contactId, receives),
    unlink: (contactId) => unlinkProductContact(id, contactId),
  }
})

function toRow(entry: ProductContactResponse): LinkedContactRow {
  return {
    contact: entry.contact,
    receivesMeetingNotes: entry.receives_meeting_notes,
    canUnlink: true,
  }
}

function concernsProduct(signal: LiveSignal): boolean {
  return signal.resource !== LiveResource.PRODUCT_CONTACTS || signal.id === props.product.id
}
</script>

<template>
  <ContactLinksSection
    :owner-key="`product-${product.id}`"
    :hint="t('contacts.links.productHint')"
    :api="api"
    :to-row="toRow"
    :customer-id="product.customer_id"
    :customer-name="product.customer?.name ?? null"
    :can-write="canWrite"
    :write-blocked="writeBlocked"
    :live-resources="[LiveResource.PRODUCT_CONTACTS, LiveResource.CONTACTS]"
    :live-filter="concernsProduct"
  />
</template>
