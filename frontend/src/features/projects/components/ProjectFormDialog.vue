<script setup lang="ts">
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { useConfirmAsync } from '@/shared/composables/useConfirmAsync'
import { computed, onMounted, reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useProjectsStore } from '../stores/projectsStore'
import { useProductsStore } from '@/features/products'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { CustomerSelect } from '@/features/customers'
import { usePermissions } from '@/core/composables/usePermissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useUsersStore } from '@/core/stores/usersStore'
import { Permission } from '@/core/auth/permissions'
import { PROJECT_STATUSES } from '../utils/projectStatus'
import { useProjectMoveReasons } from '../composables/useProjectMoveReasons'
import { useHostStore } from '@/core/host/stores/hostStore'
import { dateToParam, toLocalDayStart } from '@/core/utils/dates'
import type { ProjectResponse, ProjectStatus } from '../types/projectResponse'
import type { CustomerResponse } from '@/features/customers'
import { matchesNumberPattern } from '@/shared/utils/numberPattern'

interface Props {
  project?: ProjectResponse
  /** Prefills the project number on create, e.g. from a batch import row. */
  prefillName?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [project: ProjectResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const store = useProjectsStore()
const productsStore = useProductsStore()
const usersStore = useUsersStore()
const currentUserStore = useCurrentUserStore()
const { hasPermission } = usePermissions()
const { ask } = useConfirmAsync()

const hostStore = useHostStore()

const canManage = computed(() => hasPermission(Permission.MANAGE_PROJECTS))
const isEditMode = computed(() => !!props.project)

// The backend only rejects an update that removes the product, so an
// already headless project stays editable.
const productRequired = computed(
  () =>
    !hostStore.allowHeadlessProjects && (!isEditMode.value || props.project?.product_id != null),
)

const { statusMoveReason } = useProjectMoveReasons()

// On edit, a status the project cannot move to now stays listed but
// disabled, with the reason under its label: the missing permission, the
// live work that blocks it, or the current status. A new project takes any
// status.
const statusOptions = computed(() =>
  PROJECT_STATUSES.map((s) => {
    const reason = props.project ? statusMoveReason(props.project, s) : null
    return { label: t(`resources.projects.status.${s}`), value: s, reason, disabled: !!reason }
  }),
)

interface FormState {
  project_number: string
  product_id: number | null
  customer: CustomerResponse | null
  description: string
  designated_user_id: number | null
  status: ProjectStatus
  production_time_budget: number | null
  required_delivery_date_made: Date | null
  required_delivery_date_bought: Date | null
}

function createEmptyForm(): FormState {
  return {
    project_number: '',
    product_id: null,
    customer: null,
    description: '',
    designated_user_id: currentUserStore.user?.id ?? null,
    status: 'active',
    production_time_budget: null,
    required_delivery_date_made: null,
    required_delivery_date_bought: null,
  }
}

function formFromProject(project: ProjectResponse): FormState {
  return {
    project_number: project.project_number,
    product_id: project.product_id,
    customer: project.customer,
    description: project.description ?? '',
    designated_user_id: project.designated_user_id,
    status: project.status,
    production_time_budget: project.production_time_budget,
    required_delivery_date_made: project.required_delivery_date_made
      ? toLocalDayStart(project.required_delivery_date_made)
      : null,
    required_delivery_date_bought: project.required_delivery_date_bought
      ? toLocalDayStart(project.required_delivery_date_bought)
      : null,
  }
}

const form = reactive<FormState>(createEmptyForm())
const { submitting, errorMessage, run } = useSubmitAction()

// Archived products stay selectable, sorted last.
const { sortedOptions: productOptions, isArchived: isProductArchived } = useArchivableOptions(
  computed(() => productsStore.items),
)
const selectedProduct = computed(
  () => productOptions.value.find((p) => p.id === form.product_id) ?? null,
)

onMounted(async () => {
  await Promise.all([
    usersStore.ensureLoaded(),
    productsStore.items.length ? Promise.resolve() : productsStore.refresh(),
  ])
})

watch(visible, (isVisible) => {
  if (!isVisible) return
  errorMessage.value = null
  if (props.project) {
    Object.assign(form, formFromProject(props.project))
  } else {
    Object.assign(form, createEmptyForm())
    if (props.prefillName) form.project_number = props.prefillName
  }
})

function confirmPropagate(message: string): Promise<boolean> {
  return ask({
    group: 'project-form-propagate',
    message,
    header: t('resources.projects.propagateConfirm.header'),
    icon: 'mdi mdi-calendar-alert',
    rejectProps: {
      label: t('resources.projects.propagateConfirm.reject'),
      severity: 'secondary',
    },
    acceptProps: { label: t('resources.projects.propagateConfirm.accept') },
  })
}

async function onSubmit(): Promise<void> {
  if (!form.project_number.trim()) {
    errorMessage.value = t('resources.projects.errors.required')
    return
  }

  // Mirrors the server checks; the number is only checked when new or changed,
  // so a legacy number never blocks an unrelated edit.
  const numberChanged =
    !isEditMode.value || form.project_number.trim() !== props.project?.project_number
  if (
    numberChanged &&
    !matchesNumberPattern(form.project_number.trim(), hostStore.projectNumberPattern)
  ) {
    errorMessage.value = t('resources.projects.errors.numberPattern', {
      pattern: hostStore.projectNumberPattern,
    })
    return
  }

  if (productRequired.value && form.product_id === null) {
    errorMessage.value = t('resources.projects.errors.productRequired')
    return
  }

  await run(async () => {
    let saved: ProjectResponse

    if (isEditMode.value && props.project) {
      const newDateMade = dateToParam(form.required_delivery_date_made)
      const newDateBought = dateToParam(form.required_delivery_date_bought)
      const madeChanged =
        newDateMade !== null && newDateMade !== props.project.required_delivery_date_made
      const boughtChanged =
        newDateBought !== null && newDateBought !== props.project.required_delivery_date_bought

      let propagateMade = false
      let propagateBought = false
      if (madeChanged || boughtChanged) {
        const fields = [
          madeChanged ? t('resources.projects.fields.requiredDeliveryDateMade') : null,
          boughtChanged ? t('resources.projects.fields.requiredDeliveryDateBought') : null,
        ]
          .filter((f): f is string => !!f)
          .join(', ')
        const confirmed = await confirmPropagate(
          t('resources.projects.propagateConfirm.message', { fields }),
        )
        propagateMade = madeChanged && confirmed
        propagateBought = boughtChanged && confirmed
      }

      saved = await store.update(props.project.id, {
        project_number: form.project_number.trim(),
        product_id: form.product_id,
        customer_id: form.customer?.id ?? null,
        description: form.description.trim() || null,
        designated_user_id: form.designated_user_id ?? undefined,
        status: form.status,
        production_time_budget: form.production_time_budget,
        required_delivery_date_made: newDateMade,
        required_delivery_date_bought: newDateBought,
        propagate_delivery_date_made: propagateMade,
        propagate_delivery_date_bought: propagateBought,
        expected_edit_version: props.project.edit_version,
      })
    } else {
      saved = await store.create({
        project_number: form.project_number.trim(),
        product_id: form.product_id,
        customer_id: form.customer?.id ?? null,
        description: form.description.trim() || undefined,
        designated_user_id: form.designated_user_id ?? undefined,
        status: form.status,
        production_time_budget: form.production_time_budget,
        required_delivery_date_made: dateToParam(form.required_delivery_date_made),
        required_delivery_date_bought: dateToParam(form.required_delivery_date_bought),
      })
    }

    visible.value = false
    emit('saved', saved)
  }, t('resources.projects.errors.unknown'))
}

function onCancel(): void {
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      isEditMode ? t('resources.projects.editProject') : t('resources.projects.createProject')
    "
    :style="{ width: 'var(--dialog-width-lg)' }"
    :breakpoints="{ '60rem': '95vw' }"
  >
    <form class="project-form" @submit.prevent="onSubmit">
      <!-- Identity: only the number and the product share a row; the rest of
           the group reads top to bottom. -->
      <div class="form-fields">
        <div class="field">
          <label for="pr-number">{{ t('resources.projects.fields.projectNumber') }} *</label>
          <InputText id="pr-number" v-model="form.project_number" fluid autocomplete="off" />
        </div>

        <div class="field">
          <label id="pr-product-label" for="pr-product">
            {{ t('resources.projects.fields.product') }}{{ productRequired ? ' *' : '' }}
          </label>
          <Select
            id="pr-product"
            aria-labelledby="pr-product-label"
            v-model="form.product_id"
            :options="productOptions"
            option-label="product_number"
            option-value="id"
            :show-clear="!productRequired"
            filter
            fluid
          >
            <template #option="{ option }">
              <span>{{ option.product_number }}</span>
              <ArchivedOptionTag v-if="option.archived" />
            </template>
            <template #value>
              <span v-if="selectedProduct">{{ selectedProduct.product_number }}</span>
              <ArchivedOptionTag v-if="selectedProduct?.archived" />
            </template>
          </Select>
          <ArchivedSelectionWarning v-if="isProductArchived(selectedProduct)" />
        </div>

        <div class="field field-wide">
          <label id="pr-customer-label" for="pr-customer">{{ t('resources.projects.fields.customer') }}</label>
          <CustomerSelect v-model="form.customer" input-id="pr-customer" aria-labelledby="pr-customer-label" />
        </div>

        <div class="field field-wide">
          <label id="pr-designated-user-label" for="pr-designated-user">{{
            t('resources.projects.fields.designatedUser')
          }}</label>
          <Select
            id="pr-designated-user"
            aria-labelledby="pr-designated-user-label"
            v-model="form.designated_user_id"
            :options="usersStore.userOptions"
            option-label="text"
            option-value="value"
            :disabled="!canManage"
            fluid
          />
        </div>

        <div class="field field-wide">
          <label for="pr-description">{{ t('resources.projects.fields.description') }}</label>
          <Textarea id="pr-description" v-model="form.description" rows="3" fluid auto-resize />
        </div>

        <div class="field field-wide">
          <label id="pr-status-label" for="pr-status">{{ t('resources.projects.fields.status') }}</label>
          <Select
            id="pr-status"
            aria-labelledby="pr-status-label"
            v-model="form.status"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            option-disabled="disabled"
            fluid
          >
            <template #option="{ option }">
              <div class="status-option">
                <span>{{ option.label }}</span>
                <small v-if="option.reason" class="status-option-reason">{{ option.reason }}</small>
              </div>
            </template>
          </Select>
        </div>
      </div>

      <Divider />

      <!-- Planning: the budget and the two delivery dates, which drive the
           propagation prompt on save. -->
      <div class="form-fields form-fields-stacked">
        <div class="field">
          <label for="pr-time-budget">
            {{ t('resources.projects.fields.productionTimeBudget') }}
            <small class="field-hint">{{
              t('resources.projects.fields.productionTimeBudgetHint')
            }}</small>
          </label>
          <InputNumber
            id="pr-time-budget"
            v-model="form.production_time_budget"
            :min="0"
            suffix=" min"
            show-buttons
            fluid
          />
        </div>

        <div class="field">
          <label for="pr-delivery-date-made">
            {{ t('resources.projects.fields.requiredDeliveryDateMade') }}
            <small class="field-hint">{{
              t('resources.projects.fields.requiredDeliveryDateMadeHint')
            }}</small>
          </label>
          <DatePicker
            id="pr-delivery-date-made"
            v-model="form.required_delivery_date_made"
            show-button-bar
            show-clear
            fluid
          />
        </div>

        <div class="field">
          <label for="pr-delivery-date-bought">
            {{ t('resources.projects.fields.requiredDeliveryDateBought') }}
            <small class="field-hint">{{
              t('resources.projects.fields.requiredDeliveryDateBoughtHint')
            }}</small>
          </label>
          <DatePicker
            id="pr-delivery-date-bought"
            v-model="form.required_delivery_date_bought"
            show-button-bar
            show-clear
            fluid
          />
        </div>
      </div>

      <ConfirmDialog group="project-form-propagate" />

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
.project-form {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.form-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3) var(--space-4);
}

// The planning group has no paired fields; one per row.
.form-fields-stacked {
  grid-template-columns: 1fr;
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.field-hint {
  display: block;
  font-weight: 400;
}

.status-option {
  display: flex;
  flex-direction: column;
}

.status-option-reason {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  white-space: normal;
}

.field-wide {
  grid-column: 1 / -1;
}
</style>
