<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { getCountryDataList, getEmojiFlag } from 'countries-list'

import { OrganisationContactsSection } from '@/features/contacts'
import { useCustomersStore } from '../stores/customersStore'
import { useEntityFormDialog } from '@/shared/composables/useEntityFormDialog'
import type { CustomerResponse } from '../types/customerResponse'

const LEVEL_OPTIONS = ['A', 'B', 'C']

// Built once at module load, this list is static
const countryOptions = getCountryDataList()
  .sort((a, b) => a.name.localeCompare(b.name))
  .map((c) => ({ label: `${getEmojiFlag(c.iso2)} ${c.name}`, value: c.iso2 }))

interface Props {
  customer?: CustomerResponse
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [customer: CustomerResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const store = useCustomersStore()

interface FormState {
  name: string
  legal_name: string
  vat_id: string
  level: string
  street: string
  city: string
  postal_code: string
  country: string | null
  email: string
  phone: string
  weblink: string
}

function createEmptyForm(): FormState {
  return {
    name: '',
    legal_name: '',
    vat_id: '',
    level: 'B',
    street: '',
    city: '',
    postal_code: '',
    country: null,
    email: '',
    phone: '',
    weblink: '',
  }
}

function formFromCustomer(customer: CustomerResponse): FormState {
  return {
    name: customer.name,
    legal_name: customer.legal_name ?? '',
    vat_id: customer.vat_id ?? '',
    level: customer.level || 'B',
    street: customer.street ?? '',
    city: customer.city ?? '',
    postal_code: customer.postal_code ?? '',
    country: customer.country || null,
    email: customer.email ?? '',
    phone: customer.phone ?? '',
    weblink: customer.weblink ?? '',
  }
}

const { form, submitting, errorMessage, isEditMode, onSubmit, onCancel } = useEntityFormDialog<
  CustomerResponse,
  FormState
>({
  visible,
  entity: () => props.customer,
  emptyForm: createEmptyForm,
  formFromEntity: formFromCustomer,
  validate: (form) => (form.name.trim() ? null : t('resources.customers.errors.required')),
  save: (form, isEditMode, customer) => {
    if (isEditMode && customer) {
      return store.update(customer.id, {
        expected_edit_version: customer.edit_version,
        name: form.name.trim(),
        legal_name: form.legal_name.trim() || null,
        vat_id: form.vat_id.trim() || null,
        level: form.level,
        street: form.street.trim() || null,
        city: form.city.trim() || null,
        postal_code: form.postal_code.trim() || null,
        country: form.country || null,
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
        weblink: form.weblink.trim() || null,
      })
    }
    return store.create({
      name: form.name.trim(),
      legal_name: form.legal_name.trim() || undefined,
      vat_id: form.vat_id.trim() || undefined,
      level: form.level,
      street: form.street.trim() || undefined,
      city: form.city.trim() || undefined,
      postal_code: form.postal_code.trim() || undefined,
      country: form.country || undefined,
      email: form.email.trim() || undefined,
      phone: form.phone.trim() || undefined,
      weblink: form.weblink.trim() || undefined,
    })
  },
  onSaved: (saved) => emit('saved', saved),
  unknownErrorMessage: t('resources.customers.errors.unknown'),
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      isEditMode ? t('resources.customers.editCustomer') : t('resources.customers.createCustomer')
    "
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <form class="customer-form" @submit.prevent="onSubmit">
      <div class="form-fields">
        <div class="field field-wide">
          <label for="c-name">{{ t('resources.customers.fields.name') }} *</label>
          <InputText id="c-name" v-model="form.name" fluid autocomplete="off" />
        </div>

        <div class="field field-wide">
          <label for="c-legal-name">{{ t('resources.customers.fields.legalName') }}</label>
          <InputText id="c-legal-name" v-model="form.legal_name" fluid autocomplete="off" />
        </div>

        <div class="field">
          <label for="c-vat-id">{{ t('resources.customers.fields.vatId') }}</label>
          <InputText id="c-vat-id" v-model="form.vat_id" fluid autocomplete="off" />
        </div>

        <div class="field">
          <label id="c-level-label" for="c-level">{{ t('resources.customers.fields.level') }}</label>
          <Select id="c-level" aria-labelledby="c-level-label" v-model="form.level" :options="LEVEL_OPTIONS" fluid />
        </div>

        <div class="field field-wide">
          <label for="c-street">{{ t('resources.customers.fields.street') }}</label>
          <InputText id="c-street" v-model="form.street" fluid autocomplete="off" />
        </div>

        <div class="field">
          <label for="c-city">{{ t('resources.customers.fields.city') }}</label>
          <InputText id="c-city" v-model="form.city" fluid autocomplete="off" />
        </div>

        <div class="field">
          <label for="c-postal-code">{{ t('resources.customers.fields.postalCode') }}</label>
          <InputText id="c-postal-code" v-model="form.postal_code" fluid autocomplete="off" />
        </div>

        <div class="field field-wide">
          <label id="c-country-label" for="c-country">{{ t('resources.customers.fields.country') }}</label>
          <Select
            id="c-country"
            aria-labelledby="c-country-label"
            v-model="form.country"
            :options="countryOptions"
            option-label="label"
            option-value="value"
            show-clear
            filter
            fluid
          />
        </div>

        <div class="field">
          <label for="c-email">{{ t('resources.customers.fields.email') }}</label>
          <InputText id="c-email" v-model="form.email" type="email" fluid autocomplete="off" />
        </div>

        <div class="field">
          <label for="c-phone">{{ t('resources.customers.fields.phone') }}</label>
          <InputText id="c-phone" v-model="form.phone" fluid autocomplete="off" />
        </div>

        <div class="field field-wide">
          <label for="c-weblink">{{ t('resources.customers.fields.weblink') }}</label>
          <InputText id="c-weblink" v-model="form.weblink" fluid autocomplete="off" />
        </div>
      </div>

      <Divider />
      <OrganisationContactsSection kind="customer" :organisation-id="customer?.id ?? null" />

      <Message v-if="errorMessage" severity="error" class="mt-2">{{ errorMessage }}</Message>

      <div class="form-footer">
        <Button
          type="button"
          :label="t('common.cancel')"
          severity="secondary"
          @click="onCancel"
          :disabled="submitting"
        />
        <Button type="submit" :label="t('common.save')" :loading="submitting" />
      </div>
    </form>
  </Dialog>
</template>

<style scoped lang="scss">
.customer-form {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.form-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3) var(--space-4);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.field-wide {
  grid-column: 1 / -1;
}
</style>
