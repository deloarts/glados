<script setup lang="ts">
/**
 * Creates or edits a contact: the person with the ways to reach them, the
 * one organisation it belongs to, and for a supplier's contact the two mail
 * flags. An existing contact also shows where it is used and offers Archive
 * or Unarchive and Anonymise. Opened from a customer or supplier, the
 * organisation is that one and cannot be changed here. Without
 * write:contacts the dialog shows the contact read only.
 */
import { computed, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import LookupSelect from '@/shared/components/forms/LookupSelect.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import {
  anonymiseContact,
  archiveContact,
  createContact,
  getContactUsage,
  restoreContact,
  updateContact,
} from '../api/contactsApi'
import {
  fetchCustomerOptions,
  fetchCustomerOptionsByIds,
  fetchSupplierOptions,
  fetchSupplierOptionsByIds,
} from '../api/organisationLookup'
import { contactDisplayName } from '../utils/contactLabels'
import ContactUsedIn from './ContactUsedIn.vue'
import type { ContactResponse, ContactUsageResponse } from '../types/contactResponse'

type OrganisationChoice = 'none' | 'customer' | 'supplier'

const props = defineProps<{
  contact?: ContactResponse | null
  /** The organisation a new contact belongs to, fixed when given. */
  customerId?: number | null
  supplierId?: number | null
}>()

const emit = defineEmits<{
  saved: [contact: ContactResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const toast = useAppToast()
const confirm = useConfirm()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()
const uid = useId()

const canWrite = computed(() => hasPermission(Permission.WRITE_CONTACTS))
const writeBlocked = computed(() => missing(Permission.WRITE_CONTACTS))
const isEdit = computed(() => props.contact != null)
const anonymised = computed(() => Boolean(props.contact?.anonymised_at))
const editable = computed(() => canWrite.value && !anonymised.value)
// Opened from a customer or a supplier, the contact stays with it.
const organisationFixed = computed(() => props.customerId != null || props.supplierId != null)

const form = reactive({
  name: '',
  role: '',
  email: '',
  phone: '',
  mobile: '',
  note: '',
  organisation: 'none' as OrganisationChoice,
  customerId: null as number | null,
  supplierId: null as number | null,
  receivesRequestMails: false,
  receivesOrderMails: false,
})
const submitted = ref(false)
const saving = ref(false)
const errorMessage = ref<string | null>(null)
const usage = ref<ContactUsageResponse | null>(null)

const organisationOptions = computed(() =>
  (['none', 'customer', 'supplier'] as const).map((value) => ({
    value,
    label: t(`contacts.organisationKinds.${value}`),
  })),
)

function reset(): void {
  const contact = props.contact
  const customerId = contact ? contact.customer_id : (props.customerId ?? null)
  const supplierId = contact ? contact.supplier_id : (props.supplierId ?? null)
  Object.assign(form, {
    name: contact?.name ?? '',
    role: contact?.role ?? '',
    email: contact?.email ?? '',
    phone: contact?.phone ?? '',
    mobile: contact?.mobile ?? '',
    note: contact?.note ?? '',
    organisation: customerId != null ? 'customer' : supplierId != null ? 'supplier' : 'none',
    customerId,
    supplierId,
    receivesRequestMails: contact?.receives_request_mails ?? false,
    receivesOrderMails: contact?.receives_order_mails ?? false,
  })
  submitted.value = false
  errorMessage.value = null
  usage.value = null
}

async function loadUsage(contactId: number): Promise<void> {
  try {
    const [found] = await getContactUsage([contactId])
    if (props.contact?.id === contactId) usage.value = found ?? null
  } catch {
    usage.value = null
  }
}

watch(visible, (open) => {
  if (!open) return
  reset()
  if (props.contact) void loadUsage(props.contact.id)
})

const nameError = computed(() =>
  submitted.value && form.name.trim() === '' ? t('contacts.errors.required') : null,
)

// Belonging to a customer or a supplier needs that one picked, or the
// contact would quietly be saved as belonging to none.
const organisationError = computed(() => {
  if (!submitted.value) return null
  if (form.organisation === 'customer' && form.customerId == null) return t('contacts.errors.customerRequired')
  if (form.organisation === 'supplier' && form.supplierId == null) return t('contacts.errors.supplierRequired')
  return null
})

function text(value: string): string | null {
  return value.trim() || null
}

function payload() {
  const supplier = form.organisation === 'supplier'
  return {
    name: form.name.trim(),
    role: text(form.role),
    email: text(form.email),
    phone: text(form.phone),
    mobile: text(form.mobile),
    note: text(form.note),
    customer_id: form.organisation === 'customer' ? form.customerId : null,
    supplier_id: supplier ? form.supplierId : null,
    // The flags belong to a supplier's contact only.
    receives_request_mails: supplier && form.receivesRequestMails,
    receives_order_mails: supplier && form.receivesOrderMails,
  }
}

async function onSave(): Promise<void> {
  submitted.value = true
  if (nameError.value || organisationError.value || !editable.value) return
  saving.value = true
  errorMessage.value = null
  try {
    const saved = props.contact
      ? await updateContact(props.contact.id, {
          ...payload(),
          expected_edit_version: props.contact.edit_version,
        })
      : await createContact(payload())
    toast.success(saved.name, t(isEdit.value ? 'contacts.toasts.saved' : 'contacts.toasts.created'))
    visible.value = false
    emit('saved', saved)
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('contacts.errors.unknown')
  } finally {
    saving.value = false
  }
}

async function runAction(
  request: (id: number) => Promise<ContactResponse>,
  message: string,
): Promise<void> {
  const contact = props.contact
  if (!contact) return
  saving.value = true
  errorMessage.value = null
  try {
    const saved = await request(contact.id)
    toast.success(contactDisplayName(t, contact), message)
    visible.value = false
    emit('saved', saved)
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('contacts.errors.unknown')
  } finally {
    saving.value = false
  }
}

function onArchiveToggle(): void {
  if (props.contact?.archived) void runAction(restoreContact, t('contacts.toasts.unarchived'))
  else void runAction(archiveContact, t('contacts.toasts.archived'))
}

function onAnonymise(): void {
  const contact = props.contact
  if (!contact) return
  confirm.require({
    header: t('contacts.anonymiseConfirmHeader'),
    message: t('contacts.anonymiseConfirm', { name: contactDisplayName(t, contact) }),
    icon: 'mdi mdi-account-off-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('contacts.anonymise'), severity: 'danger' },
    accept: () => void runAction(anonymiseContact, t('contacts.toasts.anonymised')),
  })
}

const header = computed(() => {
  if (!props.contact) return t('contacts.createContact')
  return canWrite.value && !anonymised.value ? t('contacts.editContact') : t('contacts.showContact')
})
</script>

<template>
  <Dialog v-model:visible="visible" modal :header="header" :style="{ width: 'var(--dialog-width-md)' }">
    <div class="dialog-body">
      <Message v-if="isEdit && !canWrite" severity="info" size="small">{{ t('contacts.readOnly') }}</Message>

      <fieldset class="dialog-section" :disabled="!editable">
        <legend>{{ t('contacts.sections.person') }}</legend>
        <div class="form-grid">
          <div class="field">
            <label :for="`${uid}-name`">{{ t('contacts.fields.name') }} *</label>
            <InputText
              :id="`${uid}-name`"
              v-model="form.name"
              :invalid="!!nameError"
              maxlength="200"
              autocomplete="off"
              fluid
              data-testid="contact-name"
            />
            <small v-if="nameError" class="field-error">{{ nameError }}</small>
          </div>
          <div class="field">
            <label :for="`${uid}-role`">{{ t('contacts.fields.role') }}</label>
            <InputText :id="`${uid}-role`" v-model="form.role" maxlength="200" autocomplete="off" fluid />
          </div>
          <div class="field">
            <label :for="`${uid}-email`">{{ t('contacts.fields.email') }}</label>
            <InputText
              :id="`${uid}-email`"
              v-model="form.email"
              type="email"
              autocomplete="off"
              fluid
              data-testid="contact-email"
            />
          </div>
          <div class="field">
            <label :for="`${uid}-phone`">{{ t('contacts.fields.phone') }}</label>
            <InputText :id="`${uid}-phone`" v-model="form.phone" maxlength="64" autocomplete="off" fluid />
          </div>
          <div class="field">
            <label :for="`${uid}-mobile`">{{ t('contacts.fields.mobile') }}</label>
            <InputText :id="`${uid}-mobile`" v-model="form.mobile" maxlength="64" autocomplete="off" fluid />
          </div>
        </div>
        <div class="field">
          <label :for="`${uid}-note`">{{ t('contacts.fields.note') }}</label>
          <Textarea :id="`${uid}-note`" v-model="form.note" rows="2" auto-resize maxlength="4000" fluid />
        </div>
      </fieldset>

      <fieldset class="dialog-section" :disabled="!editable || organisationFixed">
        <legend>{{ t('contacts.sections.organisation') }}</legend>
        <div class="form-grid">
          <div class="field">
            <label :id="`${uid}-organisation-label`" :for="`${uid}-organisation`">
              {{ t('contacts.fields.organisation') }}
            </label>
            <Select
              v-model="form.organisation"
              :input-id="`${uid}-organisation`"
              :aria-labelledby="`${uid}-organisation-label`"
              :options="organisationOptions"
              option-label="label"
              option-value="value"
              fluid
              data-testid="contact-organisation-kind"
            />
          </div>
          <div v-if="form.organisation === 'customer'" class="field">
            <!-- A span, since the search select it names is labelled through aria-labelledby. -->
            <span :id="`${uid}-customer-label`">{{ t('contacts.fields.customer') }}</span>
            <LookupSelect
              v-model="form.customerId"
              :fetch="fetchCustomerOptions"
              :fetch-by-ids="fetchCustomerOptionsByIds"
              :aria-labelledby="`${uid}-customer-label`"
              :invalid="!!organisationError"
              size="normal"
              data-testid="contact-customer"
            />
            <small v-if="organisationError" class="field-error">{{ organisationError }}</small>
          </div>
          <div v-else-if="form.organisation === 'supplier'" class="field">
            <!-- A span, since the search select it names is labelled through aria-labelledby. -->
            <span :id="`${uid}-supplier-label`">{{ t('contacts.fields.supplier') }}</span>
            <LookupSelect
              v-model="form.supplierId"
              :fetch="fetchSupplierOptions"
              :fetch-by-ids="fetchSupplierOptionsByIds"
              :aria-labelledby="`${uid}-supplier-label`"
              :invalid="!!organisationError"
              size="normal"
              data-testid="contact-supplier"
            />
            <small v-if="organisationError" class="field-error">{{ organisationError }}</small>
          </div>
        </div>
        <small class="hint">{{ t('contacts.fields.organisationHint') }}</small>
      </fieldset>

      <fieldset v-if="form.organisation === 'supplier'" class="dialog-section" :disabled="!editable">
        <legend>{{ t('contacts.organisationKinds.supplier') }}</legend>
        <div class="flag-row">
          <ToggleSwitch
            v-model="form.receivesRequestMails"
            :input-id="`${uid}-request-mails`"
            data-testid="contact-request-mails"
          />
          <label :for="`${uid}-request-mails`">{{ t('contacts.fields.receivesRequestMails') }}</label>
        </div>
        <div class="flag-row">
          <ToggleSwitch
            v-model="form.receivesOrderMails"
            :input-id="`${uid}-order-mails`"
            data-testid="contact-order-mails"
          />
          <label :for="`${uid}-order-mails`">{{ t('contacts.fields.receivesOrderMails') }}</label>
        </div>
        <small class="hint">{{ t('contacts.fields.mailFlagsHint') }}</small>
      </fieldset>

      <fieldset v-if="contact" class="dialog-section">
        <legend>{{ t('contacts.sections.usedIn') }}</legend>
        <ContactUsedIn :contact="contact" :usage="usage" explain-empty />
      </fieldset>
    </div>

    <template #footer>
      <div v-if="contact && !anonymised" class="footer-start">
        <span v-tooltip.top="writeBlocked || undefined">
          <Button
            type="button"
            :label="contact.archived ? t('contacts.unarchive') : t('contacts.archive')"
            :icon="contact.archived ? 'mdi mdi-archive-arrow-up-outline' : 'mdi mdi-archive-outline'"
            severity="secondary"
            text
            :disabled="!canWrite || saving"
            data-testid="contact-archive-toggle"
            @click="onArchiveToggle"
          />
        </span>
        <span v-tooltip.top="writeBlocked || undefined">
          <Button
            type="button"
            :label="t('contacts.anonymise')"
            icon="mdi mdi-account-off-outline"
            severity="danger"
            text
            :disabled="!canWrite || saving"
            data-testid="contact-anonymise"
            @click="onAnonymise"
          />
        </span>
      </div>
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error">
        {{ errorMessage }}
      </Message>
      <Button
        type="button"
        :label="t('common.cancel')"
        severity="secondary"
        text
        :disabled="saving"
        @click="visible = false"
      />
      <span v-if="!anonymised" v-tooltip.top="writeBlocked || undefined">
        <Button
          type="button"
          :label="isEdit ? t('contacts.saveContact') : t('contacts.createAction')"
          icon="mdi mdi-check"
          :loading="saving"
          :disabled="!canWrite"
          data-testid="contact-save"
          @click="onSave"
        />
      </span>
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.dialog-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.flag-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.footer-start {
  display: flex;
  gap: var(--space-1);
  margin-right: auto;
}

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}

.field-error {
  color: var(--p-red-500);
  font-size: var(--font-size-sm);
}
</style>
