<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getCountryDataList, getEmojiFlag } from 'countries-list'

import { OrganisationContactsSection } from '@/features/contacts'
import { useSuppliersStore } from '../stores/suppliersStore'
import { useArticleGroupsStore } from '@/features/article-groups'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import { useEntityFormDialog } from '@/shared/composables/useEntityFormDialog'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { useHostStore } from '@/core/host/stores/hostStore'
import SupplierCapabilitiesField from './SupplierCapabilitiesField.vue'
import SupplierCommunicationFields from './SupplierCommunicationFields.vue'
import type { SupplierResponse } from '../types/supplierResponse'
import type { Schemas } from '@/core/api/generated'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

// Built once at module load, this list is static
const countryOptions = getCountryDataList()
  .sort((a, b) => a.name.localeCompare(b.name))
  .map((c) => ({ label: `${getEmojiFlag(c.iso2)} ${c.name}`, value: c.iso2 }))

interface Props {
  supplier?: SupplierResponse
  /** Prefills the name on create, e.g. from a batch import row. */
  prefillName?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [supplier: SupplierResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const store = useSuppliersStore()
const articleGroupsStore = useArticleGroupsStore()
const hostStore = useHostStore()

interface FormState {
  name: string
  legal_name: string
  vat_id: string
  level: Schemas['SupplierLevel']
  external_lead_time_days: number | null
  edp_code: string
  edp_type_number_first: boolean
  capability_ids: number[]
  article_group_ids: number[]
  street: string
  city: string
  postal_code: string
  country: string | null
  email: string
  phone: string
  weblink: string
  order_email: string
  order_language: string | null
  order_template: string
  request_email: string
  request_language: string | null
  request_template: string
}

function createEmptyForm(): FormState {
  return {
    name: props.prefillName ?? '',
    legal_name: '',
    vat_id: '',
    level: 'B',
    external_lead_time_days: null,
    edp_code: '',
    edp_type_number_first: false,
    capability_ids: [],
    article_group_ids: [],
    street: '',
    city: '',
    postal_code: '',
    country: null,
    email: '',
    phone: '',
    weblink: '',
    order_email: '',
    order_language: null,
    order_template: '',
    request_email: '',
    request_language: null,
    request_template: '',
  }
}

function formFromSupplier(supplier: SupplierResponse): FormState {
  return {
    name: supplier.name,
    legal_name: supplier.legal_name ?? '',
    vat_id: supplier.vat_id ?? '',
    level: supplier.level,
    external_lead_time_days: supplier.external_lead_time_days ?? null,
    edp_code: supplier.edp_code ?? '',
    edp_type_number_first: supplier.edp_type_number_first ?? false,
    capability_ids: supplier.capability_ids ?? [],
    article_group_ids: supplier.article_group_ids ?? [],
    street: supplier.street ?? '',
    city: supplier.city ?? '',
    postal_code: supplier.postal_code ?? '',
    country: supplier.country || null,
    email: supplier.email ?? '',
    phone: supplier.phone ?? '',
    weblink: supplier.weblink ?? '',
    order_email: supplier.order_email ?? '',
    order_language: supplier.order_language || null,
    order_template: supplier.order_template ?? '',
    request_email: supplier.request_email ?? '',
    request_language: supplier.request_language || null,
    request_template: supplier.request_template ?? '',
  }
}

const { form, submitting, errorMessage, isEditMode, onSubmit, onCancel } = useEntityFormDialog<
  SupplierResponse,
  FormState
>({
  visible,
  entity: () => props.supplier,
  emptyForm: createEmptyForm,
  formFromEntity: formFromSupplier,
  validate: (form) => (form.name.trim() ? null : t('resources.suppliers.errors.required')),
  save: (form, isEditMode, supplier) => {
    if (isEditMode && supplier) {
      return store.update(supplier.id, {
        expected_edit_version: supplier.edit_version,
        name: form.name.trim(),
        legal_name: form.legal_name.trim() || null,
        vat_id: form.vat_id.trim() || null,
        level: form.level,
        external_lead_time_days: form.external_lead_time_days,
        edp_code: form.edp_code.trim() || null,
        edp_type_number_first: form.edp_type_number_first,
        capability_ids: form.capability_ids,
        article_group_ids: form.article_group_ids,
        street: form.street.trim() || null,
        city: form.city.trim() || null,
        postal_code: form.postal_code.trim() || null,
        country: form.country || null,
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
        weblink: form.weblink.trim() || null,
        order_email: form.order_email.trim() || null,
        order_language: form.order_language || null,
        order_template: form.order_template.trim() || null,
        request_email: form.request_email.trim() || null,
        request_language: form.request_language || null,
        request_template: form.request_template.trim() || null,
      })
    }
    return store.create({
      name: form.name.trim(),
      legal_name: form.legal_name.trim() || undefined,
      vat_id: form.vat_id.trim() || undefined,
      level: form.level,
      external_lead_time_days: form.external_lead_time_days ?? undefined,
      edp_code: form.edp_code.trim() || undefined,
      edp_type_number_first: form.edp_type_number_first,
      capability_ids: form.capability_ids.length ? form.capability_ids : undefined,
      article_group_ids: form.article_group_ids.length ? form.article_group_ids : undefined,
      street: form.street.trim() || undefined,
      city: form.city.trim() || undefined,
      postal_code: form.postal_code.trim() || undefined,
      country: form.country || undefined,
      email: form.email.trim() || undefined,
      phone: form.phone.trim() || undefined,
      weblink: form.weblink.trim() || undefined,
      order_email: form.order_email.trim() || undefined,
      order_language: form.order_language || undefined,
      order_template: form.order_template.trim() || undefined,
      request_email: form.request_email.trim() || undefined,
      request_language: form.request_language || undefined,
      request_template: form.request_template.trim() || undefined,
    })
  },
  onSaved: (saved) => emit('saved', saved),
  unknownErrorMessage: t('resources.suppliers.errors.unknown'),
})

// Archived article groups stay selectable, sorted last.
const { sortedOptions: articleGroupOptions, isArchived: isArticleGroupArchived } =
  useArchivableOptions(computed(() => articleGroupsStore.items))
const selectedArticleGroups = computed(() =>
  articleGroupsStore.items.filter((g) => form.article_group_ids.includes(g.id)),
)

onMounted(async () => {
  if (!articleGroupsStore.items.length) await articleGroupsStore.refresh()
})

const requestTemplateLanguage = computed(() => form.request_language ?? form.order_language)
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      isEditMode ? t('resources.suppliers.editSupplier') : t('resources.suppliers.createSupplier')
    "
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <form class="supplier-form" @submit.prevent="onSubmit">
      <div class="form-section">
        <div class="form-fields">
          <div class="field field-wide">
            <label for="s-name">{{ t('resources.suppliers.fields.name') }} *</label>
            <InputText id="s-name" v-model="form.name" fluid autocomplete="off" />
          </div>

          <div class="field field-wide">
            <label for="s-legal-name">{{ t('resources.suppliers.fields.legalName') }}</label>
            <InputText id="s-legal-name" v-model="form.legal_name" fluid autocomplete="off" />
          </div>

          <div class="field">
            <label for="s-vat-id">{{ t('resources.suppliers.fields.vatId') }}</label>
            <InputText id="s-vat-id" v-model="form.vat_id" fluid autocomplete="off" />
          </div>

          <div class="field">
            <label id="s-level-label" for="s-level">{{ t('resources.suppliers.fields.level') }}</label>
            <Select
              id="s-level"
              aria-labelledby="s-level-label"
              v-model="form.level"
              :options="hostStore.supplierLevels"
              fluid
            />
          </div>

          <div class="field">
            <label for="s-lead-time-days">{{
              t('resources.suppliers.fields.externalLeadTimeDays')
            }}</label>
            <InputNumber
              input-id="s-lead-time-days"
              v-model="form.external_lead_time_days"
              :min="0"
              show-buttons
              fluid
            />
            <small class="hint">{{
              t('resources.suppliers.fields.externalLeadTimeDaysHint')
            }}</small>
          </div>

          <div class="field">
            <label for="s-edp-code">{{ t('resources.suppliers.fields.edpCode') }}</label>
            <InputText id="s-edp-code" v-model="form.edp_code" maxlength="16" fluid />
            <small class="hint">{{ t('resources.suppliers.fields.edpCodeHint') }}</small>
          </div>

          <div class="field">
            <div class="checkbox-label">
              <Checkbox
                v-model="form.edp_type_number_first"
                binary
                input-id="s-edp-type-number-first"
                data-testid="supplier-edp-type-number-first"
              />
              <label for="s-edp-type-number-first">{{
                t('resources.suppliers.fields.edpTypeNumberFirst')
              }}</label>
            </div>
            <small class="hint">{{ t('resources.suppliers.fields.edpTypeNumberFirstHint') }}</small>
          </div>

          <SupplierCapabilitiesField v-model="form.capability_ids" />

          <div class="field field-wide">
            <label id="s-article-groups-label" for="s-article-groups">{{
              t('resources.suppliers.fields.articleGroups')
            }}</label>
            <MultiSelect
              id="s-article-groups"
              aria-labelledby="s-article-groups-label"
              v-model="form.article_group_ids"
              :options="articleGroupOptions"
              :option-label="labelName"
              option-value="id"
              display="chip"
              :placeholder="t('resources.suppliers.fields.articleGroupsPlaceholder')"
              filter
              fluid
            >
              <template #option="{ option }">
                <span>{{ localizeLabel(option.name) }}</span>
                <ArchivedOptionTag v-if="option.archived" />
              </template>
            </MultiSelect>
            <ArchivedSelectionWarning v-if="isArticleGroupArchived(selectedArticleGroups)" />
          </div>
        </div>
      </div>

      <Divider />

      <div class="form-section">
        <div class="form-fields">
          <div class="field field-wide">
            <label for="s-street">{{ t('resources.suppliers.fields.street') }}</label>
            <InputText id="s-street" v-model="form.street" fluid autocomplete="off" />
          </div>

          <div class="field">
            <label for="s-city">{{ t('resources.suppliers.fields.city') }}</label>
            <InputText id="s-city" v-model="form.city" fluid autocomplete="off" />
          </div>

          <div class="field">
            <label for="s-postal-code">{{ t('resources.suppliers.fields.postalCode') }}</label>
            <InputText id="s-postal-code" v-model="form.postal_code" fluid autocomplete="off" />
          </div>

          <div class="field field-wide">
            <label id="s-country-label" for="s-country">{{ t('resources.suppliers.fields.country') }}</label>
            <Select
              id="s-country"
              aria-labelledby="s-country-label"
              v-model="form.country"
              :options="countryOptions"
              option-label="label"
              option-value="value"
              show-clear
              filter
              fluid
            />
          </div>
        </div>
      </div>

      <Divider />

      <div class="form-section">
        <div class="form-fields">
          <div class="field">
            <label for="s-email">{{ t('resources.suppliers.fields.email') }}</label>
            <InputText id="s-email" v-model="form.email" type="email" fluid autocomplete="off" />
          </div>

          <div class="field">
            <label for="s-phone">{{ t('resources.suppliers.fields.phone') }}</label>
            <InputText id="s-phone" v-model="form.phone" fluid autocomplete="off" />
          </div>

          <div class="field field-wide">
            <label for="s-weblink">{{ t('resources.suppliers.fields.weblink') }}</label>
            <InputText id="s-weblink" v-model="form.weblink" fluid autocomplete="off" />
          </div>
        </div>
      </div>

      <Divider />

      <div class="form-section">
        <div class="form-fields">
          <SupplierCommunicationFields
            id-prefix="s-order"
            v-model:email="form.order_email"
            v-model:language="form.order_language"
            v-model:template="form.order_template"
            :template-language="form.order_language"
            :email-label="t('resources.suppliers.fields.orderEmail')"
            :language-label="t('resources.suppliers.fields.orderLanguage')"
            :template-label="t('resources.suppliers.fields.orderTemplate')"
          />

          <SupplierCommunicationFields
            id-prefix="s-request"
            v-model:email="form.request_email"
            v-model:language="form.request_language"
            v-model:template="form.request_template"
            :template-language="requestTemplateLanguage"
            :email-label="t('resources.suppliers.fields.requestEmail')"
            :language-label="t('resources.suppliers.fields.requestLanguage')"
            :template-label="t('resources.suppliers.fields.requestTemplate')"
          />
        </div>
      </div>

      <Divider />

      <div class="form-section">
        <OrganisationContactsSection kind="supplier" :organisation-id="supplier?.id ?? null" />
      </div>

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
.supplier-form {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.form-section {
  padding: var(--space-1) 0;
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

.checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
