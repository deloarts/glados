<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useProductsStore } from '../stores/productsStore'
import { CustomerSelect } from '@/features/customers'
import { usePermissions } from '@/core/composables/usePermissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useUsersStore } from '@/core/stores/usersStore'
import { Permission } from '@/core/auth/permissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import ItemImageSection from '@/shared/components/files/ItemImageSection.vue'
import { useProductFilesStore } from '../stores/productFilesStore'
import { getProductFileBlob } from '../api/getProductFileBlob'
import { useEntityFormDialog } from '@/shared/composables/useEntityFormDialog'
import { getPickerDateFormat, toDateKey } from '@/core/utils/dates'
import type { ProductResponse } from '../types/productResponse'
import { usePlcEnvironmentsStore } from '@/features/product-devices'
import { LEGAL_BASES, legalBasisFor, legalBasisOutdated } from '../utils/legalBasis'
import type { LegalBasis } from '../utils/legalBasis'
import type { CustomerResponse } from '@/features/customers'
import { matchesNumberPattern } from '@/shared/utils/numberPattern'
import { extractApiError } from '@/core/utils/errors'
import { getRenumberImpact, type ProductRenumberImpact } from '../api/getRenumberImpact'
import ProductRenumberDialog from './ProductRenumberDialog.vue'

interface Props {
  product?: ProductResponse
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [product: ProductResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const store = useProductsStore()
const usersStore = useUsersStore()
const currentUserStore = useCurrentUserStore()
const { hasPermission } = usePermissions()
const hostStore = useHostStore()

const canManage = computed(() => hasPermission(Permission.MANAGE_PROJECTS))

const filesStore = useProductFilesStore()

// A product's designated user may attach files without manage:projects, as
// the backend allows.
const canEditFiles = computed(
  () => canManage.value || props.product?.designated_user_id === currentUserStore.user?.id,
)

interface FormState {
  product_number: string
  customer: CustomerResponse | null
  description: string
  designated_user_id: number | null
  is_active: boolean
  designation: string
  machine_type: string
  installation_site: string
  installation_location: string
  planned_placing_on_market: Date | null
  legal_basis: LegalBasis
  plc_environment_id: number | null
  contains_pneumatics: boolean
  contains_hydraulics: boolean
  contains_electrics: boolean
  contains_robotics: boolean
}

const MACHINE_TEXT_FIELDS = [
  { key: 'designation', label: 'designation' },
  { key: 'machine_type', label: 'machineType' },
  { key: 'installation_site', label: 'installationSite' },
  { key: 'installation_location', label: 'installationLocation' },
] as const

/** Longest value of a machine data text field, the length the checklist header keeps. */
const MAX_MACHINE_FIELD_LENGTH = 200

function createEmptyForm(): FormState {
  return {
    product_number: '',
    customer: null,
    description: '',
    designated_user_id: currentUserStore.user?.id ?? null,
    is_active: true,
    designation: '',
    machine_type: '',
    installation_site: '',
    installation_location: '',
    planned_placing_on_market: null,
    legal_basis: legalBasisFor(null),
    plc_environment_id: null,
    contains_pneumatics: false,
    contains_hydraulics: false,
    contains_electrics: false,
    contains_robotics: false,
  }
}

function dateFromIso(iso: string | null): Date | null {
  if (!iso) return null
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year ?? 0, (month ?? 1) - 1, day ?? 1)
}

function formFromProduct(product: ProductResponse): FormState {
  return {
    product_number: product.product_number,
    customer: product.customer,
    description: product.description ?? '',
    designated_user_id: product.designated_user_id,
    is_active: product.is_active,
    designation: product.designation ?? '',
    machine_type: product.machine_type ?? '',
    installation_site: product.installation_site ?? '',
    installation_location: product.installation_location ?? '',
    planned_placing_on_market: dateFromIso(product.planned_placing_on_market),
    legal_basis: product.legal_basis ?? legalBasisFor(product.planned_placing_on_market),
    plc_environment_id: product.plc_environment_id,
    contains_pneumatics: product.contains_pneumatics,
    contains_hydraulics: product.contains_hydraulics,
    contains_electrics: product.contains_electrics,
    contains_robotics: product.contains_robotics,
  }
}

onMounted(async () => {
  environments.load().catch(() => {})
  await usersStore.ensureLoaded()
})

/** The disciplines a machine can have; they pick the plans a device rename must reach. */
const DISCIPLINE_FLAGS = ['contains_pneumatics', 'contains_hydraulics', 'contains_electrics', 'contains_robotics'] as const

// ── PLC environment ───────────────────────────────────────────────────

const environments = usePlcEnvironmentsStore()

// Empty means the default environment. An environment archived after it was
// chosen stays offered for this product only.
const environmentOptions = computed(() => {
  const fallback = environments.defaultEnvironment
  const options: Array<{ value: number | null; label: string }> = [
    {
      value: null,
      label: fallback
        ? t('resources.products.fields.plcEnvironmentDefault', { name: fallback.name })
        : t('resources.products.fields.plcEnvironmentNone'),
    },
  ]
  for (const environment of environments.environments) {
    if (environment.archived && environment.id !== props.product?.plc_environment_id) continue
    options.push({ value: environment.id, label: environment.name })
  }
  return options
})

const { form, submitting, errorMessage, isEditMode, onSubmit, onCancel } = useEntityFormDialog<
  ProductResponse,
  FormState
>({
  visible,
  entity: () => props.product,
  emptyForm: createEmptyForm,
  formFromEntity: formFromProduct,
  validate: (form, isEditMode, product) => {
    if (!form.product_number.trim()) return t('resources.products.errors.required')

    // Mirrors the server rule; checked when new or changed, so an older number
    // stays editable.
    const numberChanged = !isEditMode || form.product_number.trim() !== product?.product_number
    if (
      numberChanged &&
      !matchesNumberPattern(form.product_number.trim(), hostStore.productNumberPattern)
    ) {
      return t('resources.products.errors.numberPattern', {
        pattern: hostStore.productNumberPattern,
      })
    }
    return null
  },
  save: (form, isEditMode, product) => {
    const payload = {
      product_number: form.product_number.trim(),
      customer_id: form.customer?.id ?? null,
      description: form.description.trim() || null,
      designated_user_id: form.designated_user_id ?? undefined,
      is_active: form.is_active,
      designation: form.designation.trim() || null,
      machine_type: form.machine_type.trim() || null,
      installation_site: form.installation_site.trim() || null,
      installation_location: form.installation_location.trim() || null,
      planned_placing_on_market: plannedIso(form),
      legal_basis: form.legal_basis,
      plc_environment_id: form.plc_environment_id,
      contains_pneumatics: form.contains_pneumatics,
      contains_hydraulics: form.contains_hydraulics,
      contains_electrics: form.contains_electrics,
      contains_robotics: form.contains_robotics,
    }
    return isEditMode && product
      ? store.update(product.id, { ...payload, expected_edit_version: product.edit_version })
      : store.create({ ...payload, description: payload.description ?? undefined })
  },
  onSaved: (saved) => emit('saved', saved),
  unknownErrorMessage: t('resources.products.errors.unknown'),
})

// ── Renumbering ───────────────────────────────────────────────────────

const renumberVisible = ref(false)
const renumberImpact = ref<ProductRenumberImpact | null>(null)
let answerRenumber: ((confirmed: boolean) => void) | null = null

function onRenumberAnswer(confirmed: boolean): void {
  answerRenumber?.(confirmed)
  answerRenumber = null
}

/**
 * Asks before an existing product gets a new number, showing what that
 * affects. True when there is nothing to ask or the user confirms.
 */
async function confirmRenumber(): Promise<boolean> {
  const product = props.product
  const newNumber = form.product_number.trim()
  if (!product || !newNumber || newNumber === product.product_number) return true
  try {
    renumberImpact.value = await getRenumberImpact(product.id, newNumber)
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('resources.products.errors.unknown')
    return false
  }
  renumberVisible.value = true
  return new Promise<boolean>((resolve) => {
    answerRenumber = resolve
  })
}

async function onSubmitWithRenumberCheck(): Promise<void> {
  if (isEditMode.value && !(await confirmRenumber())) return
  await onSubmit()
}

function plannedIso(state: FormState): string | null {
  return state.planned_placing_on_market ? toDateKey(state.planned_placing_on_market) : null
}

const legalOptions = computed(() =>
  LEGAL_BASES.map((value) => ({ value, label: t(`resources.products.legalBases.${value}`) })),
)

// A new planned date preselects the legal act that applies on that date; the
// selection can still be changed by hand afterwards.
function updatePlacing(value: unknown) {
  form.planned_placing_on_market = value instanceof Date ? value : null
  form.legal_basis = legalBasisFor(plannedIso(form))
}

function updateLegalBasis(value: unknown) {
  if (value === 'directive' || value === 'regulation') form.legal_basis = value
}

const legalBasisWarning = computed(() => legalBasisOutdated(form.legal_basis, plannedIso(form)))
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      isEditMode ? t('resources.products.editProduct') : t('resources.products.createProduct')
    "
    :style="{ width: 'var(--dialog-width-lg)' }"
    :breakpoints="{ '60rem': '95vw' }"
  >
    <form class="product-form" @submit.prevent="onSubmitWithRenumberCheck">
      <div class="form-fields">
        <div class="field">
          <label for="p-number">{{ t('resources.products.fields.productNumber') }} *</label>
          <InputText id="p-number" v-model="form.product_number" fluid autocomplete="off" />
        </div>

        <div class="field">
          <label id="p-customer-label" for="p-customer">{{ t('resources.products.fields.customer') }}</label>
          <CustomerSelect v-model="form.customer" input-id="p-customer" aria-labelledby="p-customer-label" />
        </div>

        <div class="field">
          <label id="p-designated-user-label" for="p-designated-user">{{ t('resources.products.fields.designatedUser') }}</label>
          <Select
            id="p-designated-user"
            aria-labelledby="p-designated-user-label"
            v-model="form.designated_user_id"
            :options="usersStore.userOptions"
            option-label="text"
            option-value="value"
            :disabled="!canManage"
            fluid
          />
        </div>

        <div class="field">
          <label for="p-description">{{ t('resources.products.fields.description') }}</label>
          <Textarea id="p-description" v-model="form.description" rows="3" fluid auto-resize />
        </div>

        <div class="field field-inline">
          <label for="p-active">{{ t('resources.products.fields.active') }}</label>
          <ToggleSwitch id="p-active" v-model="form.is_active" />
        </div>
      </div>

      <Divider />
      <div class="form-fields" data-testid="p-machine-data">
        <div class="section-heading">
          <span class="section-title">{{ t('resources.products.machineData.title') }}</span>
          <small class="hint">{{ t('resources.products.machineData.hint') }}</small>
        </div>

        <div v-for="field in MACHINE_TEXT_FIELDS" :key="field.key" class="field">
          <label :for="`p-${field.key}`">{{ t(`resources.products.fields.${field.label}`) }}</label>
          <InputText
            :id="`p-${field.key}`"
            v-model="form[field.key]"
            :maxlength="MAX_MACHINE_FIELD_LENGTH"
            fluid
            autocomplete="off"
            :data-testid="`p-${field.key}`"
          />
        </div>

        <div class="field">
          <label for="p-placing">{{ t('resources.products.fields.placingOnMarket') }}</label>
          <DatePicker
            :model-value="form.planned_placing_on_market"
            input-id="p-placing"
            :date-format="getPickerDateFormat()"
            show-button-bar
            show-clear
            fluid
            data-testid="p-placing"
            @update:model-value="updatePlacing"
          />
        </div>

        <div class="field">
          <span id="p-legal-basis-label" class="field-label">{{ t('resources.products.fields.legalBasis') }}</span>
          <SelectButton
            :model-value="form.legal_basis"
            :options="legalOptions"
            option-value="value"
            option-label="label"
            :allow-empty="false"
            aria-labelledby="p-legal-basis-label"
            data-testid="p-legal-basis"
            @update:model-value="updateLegalBasis"
          />
          <small class="hint">{{ t('resources.products.machineData.legalBasisHint') }}</small>
          <Message v-if="legalBasisWarning" severity="warn" data-testid="p-legal-basis-warning">
            {{ t('resources.products.machineData.legalBasisOutdated') }}
          </Message>
        </div>

        <!-- The PLC environment names the product's device tags, so it goes
             with the devices feature; a stored value is kept as it is. -->
        <div v-if="hostStore.devicesEnabled" class="field">
          <label id="p-plc-environment-label" for="p-plc-environment">{{ t('resources.products.fields.plcEnvironment') }}</label>
          <Select
            v-model="form.plc_environment_id"
            input-id="p-plc-environment"
            aria-labelledby="p-plc-environment-label"
            :options="environmentOptions"
            option-label="label"
            option-value="value"
            fluid
            data-testid="p-plc-environment"
          />
          <small class="hint">{{ t('resources.products.fields.plcEnvironmentHint') }}</small>
        </div>

        <div class="field">
          <span class="field-label">{{ t('resources.products.fields.disciplines') }}</span>
          <div class="disciplines">
            <label v-for="flag in DISCIPLINE_FLAGS" :key="flag" class="discipline">
              <Checkbox v-model="form[flag]" binary :data-testid="`p-${flag}`" />
              {{ t(`resources.products.disciplines.${flag}`) }}
            </label>
          </div>
          <small class="hint">{{ t('resources.products.fields.disciplinesHint') }}</small>
        </div>
      </div>

      <!-- Files need a saved product, so creation shows a hint instead. -->
      <template v-if="hostStore.storageEnabled">
        <Divider />
        <ItemImageSection
          v-if="props.product"
          :item-id="props.product.id"
          :files-store="filesStore"
          :can-edit="canEditFiles"
          i18n-prefix="resources.products.files"
          :fetch-blob="getProductFileBlob"
        />
        <span v-else class="files-hint">{{ t('common.files.addAfterSaving') }}</span>
      </template>

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

  <ProductRenumberDialog
    v-model:visible="renumberVisible"
    :impact="renumberImpact"
    :old-number="product?.product_number ?? ''"
    :new-number="form.product_number.trim()"
    @confirm="onRenumberAnswer(true)"
    @cancel="onRenumberAnswer(false)"
  />
</template>

<style scoped lang="scss">
.disciplines {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
}

.discipline {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.product-form {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.files-hint {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

// One field per row, so inputs are not narrower than the file slots below.
.form-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.field {
  label,
  .field-label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.section-heading {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.section-title {
  font-weight: 600;
}

// The toggle should sit at its natural width rather than stretching.
.field-inline {
  align-items: flex-start;
}
</style>
