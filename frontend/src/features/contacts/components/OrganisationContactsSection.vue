<script setup lang="ts">
/**
 * The contacts of one customer or supplier, as a section of its dialog:
 * a short table with New Contact, a row opening the contact's dialog, and
 * for a supplier the two switches that decide who receives its request and
 * order mails. A new organisation has no contacts until it is saved, and a
 * user without read:contacts sees why the section is empty.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { fetchAllPages } from '@/core/api/fetchAllPages'
import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { extractApiError } from '@/core/utils/errors'
import ContactLinks from '@/shared/components/ContactLinks.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import { getContacts, updateContact } from '../api/contactsApi'
import { contactDisplayName } from '../utils/contactLabels'
import ContactFormDialog from './ContactFormDialog.vue'
import type { ContactResponse } from '../types/contactResponse'
import type { DataTableRowClickEvent } from 'openvue/datatable'

type MailFlag = 'receives_request_mails' | 'receives_order_mails'

const props = defineProps<{
  kind: 'customer' | 'supplier'
  /** The saved organisation's id, null while it is being created. */
  organisationId: number | null
}>()

const { t } = useI18n()
const toast = useAppToast()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()

const canRead = computed(() => hasPermission(Permission.READ_CONTACTS))
const canWrite = computed(() => hasPermission(Permission.WRITE_CONTACTS))
const writeBlocked = computed(() => missing(Permission.WRITE_CONTACTS))

const contacts = ref<ContactResponse[]>([])
const loading = ref(false)
const savingId = ref<number | null>(null)
const dialogVisible = ref(false)
const editing = ref<ContactResponse | null>(null)

async function load(): Promise<void> {
  const id = props.organisationId
  if (id === null || !canRead.value) {
    contacts.value = []
    return
  }
  loading.value = true
  try {
    const filter = props.kind === 'customer' ? { customer_id: id } : { supplier_id: id }
    const rows = await fetchAllPages((page) => getContacts({ ...filter, ...page, order_by: 'name' }))
    if (props.organisationId === id) contacts.value = rows
  } catch {
    contacts.value = []
  } finally {
    loading.value = false
  }
}

watch(() => [props.kind, props.organisationId], () => void load(), { immediate: true })
useLiveRefresh([LiveResource.CONTACTS], load, { debounceMs: 300 })

function openNew(): void {
  editing.value = null
  dialogVisible.value = true
}

// A click on a mail switch changes the flag and leaves the row closed.
function onRowClick(event: DataTableRowClickEvent<ContactResponse>): void {
  const target = event.originalEvent.target
  if (target instanceof Element && target.closest('[data-keeps-row-closed]')) return
  openContact(event.data)
}

function openContact(contact: ContactResponse): void {
  editing.value = contact
  dialogVisible.value = true
}

async function setFlag(contact: ContactResponse, flag: MailFlag, value: boolean): Promise<void> {
  savingId.value = contact.id
  try {
    const saved = await updateContact(contact.id, {
      name: contact.name,
      role: contact.role,
      email: contact.email,
      phone: contact.phone,
      mobile: contact.mobile,
      note: contact.note,
      customer_id: contact.customer_id,
      supplier_id: contact.supplier_id,
      receives_request_mails: contact.receives_request_mails,
      receives_order_mails: contact.receives_order_mails,
      [flag]: value,
      expected_edit_version: contact.edit_version,
    })
    contacts.value = contacts.value.map((row) => (row.id === saved.id ? saved : row))
    toast.success(contactDisplayName(t, saved), t('contacts.organisationSection.flagSaved'))
  } catch (err) {
    toast.error(contactDisplayName(t, contact), extractApiError(err) ?? t('contacts.errors.unknown'))
  } finally {
    savingId.value = null
  }
}

const saveFirstNote = computed(() =>
  props.kind === 'customer'
    ? t('contacts.organisationSection.saveCustomerFirst')
    : t('contacts.organisationSection.saveSupplierFirst'),
)
</script>

<template>
  <section class="organisation-contacts" data-testid="organisation-contacts">
    <div class="section-head">
      <span class="section-label">{{ t('contacts.organisationSection.title') }}</span>
      <span v-if="canRead && organisationId !== null" v-tooltip.top="writeBlocked || undefined">
        <Button
          type="button"
          :label="t('contacts.createContact')"
          icon="mdi mdi-plus"
          severity="contrast"
          size="small"
          text
          :disabled="!canWrite"
          data-testid="organisation-contacts-new"
          @click="openNew"
        />
      </span>
    </div>

    <p v-if="!canRead" class="empty-note" data-testid="organisation-contacts-no-access">
      {{
        t('contacts.organisationSection.noAccess', {
          permission: permissionLabel(t, Permission.READ_CONTACTS),
        })
      }}
    </p>
    <p v-else-if="organisationId === null" class="empty-note">{{ saveFirstNote }}</p>
    <DataTable
      v-else
      :value="contacts"
      :loading="loading"
      data-key="id"
      size="small"
      selection-mode="single"
      class="clickable-rows"
      data-testid="organisation-contacts-table"
      @row-click="onRowClick"
    >
      <template #empty>
        <span class="empty-note">{{ t('contacts.organisationSection.empty') }}</span>
      </template>
      <Column header="#" body-class="row-number" class="column-fit">
        <template #body="{ index }">{{ index + 1 }}</template>
      </Column>
      <Column :header="t('contacts.columns.name')" class="column-fit">
        <template #body="{ data }: { data: ContactResponse }">
          <div class="name-cell">
            <span class="contact-name">{{ contactDisplayName(t, data) }}</span>
            <small v-if="data.role" class="text-muted">{{ data.role }}</small>
          </div>
        </template>
      </Column>
      <Column :header="t('contacts.columns.email')" class="column-fit">
        <template #body="{ data }: { data: ContactResponse }">
          <ContactLinks :email="data.email" />
        </template>
      </Column>
      <Column v-if="kind === 'customer'" :header="t('contacts.columns.phone')" class="column-fit">
        <template #body="{ data }: { data: ContactResponse }">
          <span v-if="data.phone || data.mobile">{{ data.phone ?? data.mobile }}</span>
          <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
        </template>
      </Column>
      <template v-if="kind === 'supplier'">
        <Column :header="t('contacts.usedIn.requestMails')" class="column-fit">
          <template #body="{ data }: { data: ContactResponse }">
            <span v-tooltip.top="writeBlocked || undefined" data-keeps-row-closed>
              <ToggleSwitch
                :model-value="data.receives_request_mails"
                :disabled="!canWrite || savingId === data.id"
                :aria-label="t('contacts.fields.receivesRequestMails')"
                data-testid="organisation-contact-request-mails"
                @update:model-value="(value: boolean) => setFlag(data, 'receives_request_mails', value)"
              />
            </span>
          </template>
        </Column>
        <Column :header="t('contacts.usedIn.orderMails')" class="column-fit">
          <template #body="{ data }: { data: ContactResponse }">
            <span v-tooltip.top="writeBlocked || undefined" data-keeps-row-closed>
              <ToggleSwitch
                :model-value="data.receives_order_mails"
                :disabled="!canWrite || savingId === data.id"
                :aria-label="t('contacts.fields.receivesOrderMails')"
                data-testid="organisation-contact-order-mails"
                @update:model-value="(value: boolean) => setFlag(data, 'receives_order_mails', value)"
              />
            </span>
          </template>
        </Column>
      </template>
      <Column />
    </DataTable>
    <small v-if="kind === 'supplier' && canRead && organisationId !== null" class="hint">
      {{ t('contacts.fields.mailFlagsHint') }}
    </small>

    <ContactFormDialog
      v-model:visible="dialogVisible"
      :contact="editing"
      :customer-id="kind === 'customer' ? organisationId : null"
      :supplier-id="kind === 'supplier' ? organisationId : null"
      @saved="load"
    />
  </section>
</template>

<style scoped lang="scss">
.organisation-contacts {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.name-cell {
  display: flex;
  flex-direction: column;
}

.contact-name {
  font-weight: 600;
}
</style>
