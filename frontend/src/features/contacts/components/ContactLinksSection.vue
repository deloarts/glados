<script setup lang="ts" generic="TEntry">
/**
 * The Contacts section of a product's or a project's overview: the linked
 * contacts with their meeting notes switch and Unlink, and Link Contact,
 * which offers the record's customer's contacts first. The owner's feature
 * passes the calls of its own contact routes, each of which answers the
 * whole list afterwards, and how one entry becomes a row. Without
 * read:contacts the section says why it is empty.
 */
import { computed, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import type { LiveSignal } from '@/core/realtime/types'
import { extractApiError } from '@/core/utils/errors'
import OverviewSection from '@/shared/components/resource-view/OverviewSection.vue'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import { contactDisplayName } from '../utils/contactLabels'
import ContactPickerDialog from './ContactPickerDialog.vue'
import LinkedContactsTable from './LinkedContactsTable.vue'
import type { LinkedContactRow } from './LinkedContactsTable.vue'
import type { ContactSummaryResponse } from '../types/contactResponse'

export interface ContactLinksApi<TEntry> {
  list: () => Promise<TEntry[]>
  link: (contactId: number, receivesMeetingNotes: boolean) => Promise<TEntry[]>
  setMeetingNotes: (contactId: number, receivesMeetingNotes: boolean) => Promise<TEntry[]>
  unlink: (contactId: number) => Promise<TEntry[]>
}

const props = defineProps<{
  /** Identifies the record; a change reloads the list. */
  ownerKey: string
  hint: string
  api: ContactLinksApi<TEntry>
  toRow: (entry: TEntry) => LinkedContactRow
  customerId: number | null
  customerName: string | null
  showSource?: boolean
  /** The live topics whose signals reload the list, and which of them concern this record. */
  liveResources: string[]
  liveFilter?: (signal: LiveSignal) => boolean
  /** Whether the user may change the record's links, which follows the record's own edit rights. */
  canWrite: boolean
  /** Why linking is not possible, shown in the tooltip of the disabled buttons. */
  writeBlocked: string
}>()

const { t } = useI18n()
const toast = useAppToast()
const confirm = useConfirm()
const { hasPermission } = usePermissions()

const canRead = computed(() => hasPermission(Permission.READ_CONTACTS))
const canWrite = computed(() => props.canWrite)
const writeBlocked = computed(() => props.writeBlocked)

const entries = ref([]) as Ref<TEntry[]>
const savingId = ref<number | null>(null)
const pickerVisible = ref(false)
const linking = ref(false)
const linkError = ref<string | null>(null)

const rows = computed(() => entries.value.map(props.toRow))
const linkedIds = computed(() => rows.value.map((row) => row.contact.id))

async function load(): Promise<void> {
  if (!canRead.value) return
  const key = props.ownerKey
  try {
    const loaded = await props.api.list()
    if (props.ownerKey === key) entries.value = loaded
  } catch {
    if (props.ownerKey === key) entries.value = []
  }
}

watch(() => props.ownerKey, () => void load(), { immediate: true })
useLiveRefresh(props.liveResources, load, { debounceMs: 300, filter: props.liveFilter })

async function onToggle(contactId: number, receivesMeetingNotes: boolean): Promise<void> {
  savingId.value = contactId
  try {
    entries.value = await props.api.setMeetingNotes(contactId, receivesMeetingNotes)
    toast.success(t('contacts.links.title'), t('contacts.links.saved'))
  } catch (err) {
    toast.error(t('contacts.links.title'), extractApiError(err) ?? t('contacts.errors.unknown'))
    await load()
  } finally {
    savingId.value = null
  }
}

async function unlink(contact: ContactSummaryResponse): Promise<void> {
  savingId.value = contact.id
  try {
    entries.value = await props.api.unlink(contact.id)
  } catch (err) {
    toast.error(contactDisplayName(t, contact), extractApiError(err) ?? t('contacts.errors.unknown'))
  } finally {
    savingId.value = null
  }
}

function onUnlink(contact: ContactSummaryResponse): void {
  confirm.require({
    header: t('contacts.links.unlink'),
    message: t('contacts.links.unlinkConfirm', { name: contactDisplayName(t, contact) }),
    icon: 'mdi mdi-link-variant-off',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('contacts.links.unlink'), severity: 'danger' },
    accept: () => void unlink(contact),
  })
}

function openPicker(): void {
  linkError.value = null
  pickerVisible.value = true
}

async function onLink(contactId: number, receivesMeetingNotes: boolean): Promise<void> {
  linking.value = true
  linkError.value = null
  try {
    entries.value = await props.api.link(contactId, receivesMeetingNotes)
    pickerVisible.value = false
  } catch (err) {
    linkError.value = extractApiError(err) ?? t('contacts.errors.unknown')
  } finally {
    linking.value = false
  }
}
</script>

<template>
  <OverviewSection :title="t('contacts.links.title')" :hint="hint" data-testid="contact-links-section">
    <template #title-end>
      <span v-if="canRead" v-tooltip.top="writeBlocked || undefined">
        <Button
          :label="t('contacts.links.linkContact')"
          icon="mdi mdi-link-variant-plus"
          severity="contrast"
          size="small"
          text
          :disabled="!canWrite"
          data-testid="contact-links-link"
          @click="openPicker"
        />
      </span>
    </template>

    <p v-if="!canRead" class="empty-note" data-testid="contact-links-no-access">
      {{ t('contacts.organisationSection.noAccess', { permission: permissionLabel(t, Permission.READ_CONTACTS) }) }}
    </p>
    <LinkedContactsTable
      v-else
      :rows="rows"
      :can-write="canWrite"
      :write-blocked="writeBlocked"
      :saving-id="savingId"
      :show-source="showSource"
      @toggle="onToggle"
      @unlink="onUnlink"
    />

    <ContactPickerDialog
      v-model:visible="pickerVisible"
      :customer-id="customerId"
      :customer-name="customerName"
      :exclude-ids="linkedIds"
      :saving="linking"
      :error-message="linkError"
      @link="onLink"
    />
  </OverviewSection>
</template>
