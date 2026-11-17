<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDebounceFn } from '@vueuse/core'

import { useHostStore } from '@/core/host/stores/hostStore'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import { useConfirmAsync } from '@/shared/composables/useConfirmAsync'
import { useEntityFormDialog } from '@/shared/composables/useEntityFormDialog'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import {
  createProductDevice,
  previewProductDeviceName,
  updateProductDevice,
} from '../api/productDevicesApi'
import { useProductDeviceResourcesStore } from '../stores/productDeviceResourcesStore'
import type {
  ProductDevice,
  ProductDeviceNamePreview,
  ProductDisciplines,
  SequenceCoverage,
} from '../types/productDevice'
import {
  deviceFormFromDevice,
  deviceSaveRequest,
  emptyDeviceForm,
  lacksSignalMeaning,
  resetKindSpecificFields,
  type ProductDeviceForm,
} from '../utils/deviceForm'
import ProductDeviceComponentsEditor from './ProductDeviceComponentsEditor.vue'
import ProductDeviceDrivenBy from './ProductDeviceDrivenBy.vue'
import ProductDeviceImagesSection from './ProductDeviceImagesSection.vue'

/**
 * Creates or edits a device of a product. The name is built by the backend
 * from location, name, driving medium and number; a debounced preview shows
 * the result in UTF-8 and ASCII while typing, and whether it is taken.
 */
const props = defineProps<{
  productId: number
  device?: ProductDevice
  readonly?: boolean
  /** The product's devices, for the device this one may be driven by. */
  devices?: ProductDevice[]
  /** The disciplines the machine has, which pick the plans a rename must reach. */
  disciplines?: ProductDisciplines
  /** Whether a flow sequence moves or checks the device. */
  sequenceCoverage?: SequenceCoverage
}>()

const emit = defineEmits<{ saved: [device: ProductDevice] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const { localize } = useLocalizedText()
const resources = useProductDeviceResourcesStore()

const { form, submitting, errorMessage, isEditMode, onSubmit, onCancel } = useEntityFormDialog<
  ProductDevice,
  ProductDeviceForm
>({
  visible,
  entity: () => props.device,
  emptyForm: emptyDeviceForm,
  formFromEntity: deviceFormFromDevice,
  validate: (form) => {
    if (!form.name.trim()) return t('productDevices.devices.errors.nameRequired')
    if (form.kind_id === null) return t('productDevices.devices.errors.kindRequired')
    if (needsMedium.value && form.driving_medium_id === null) {
      return t('productDevices.devices.errors.mediumRequired')
    }
    if (form.components.some((c) => c.role_id === null)) {
      return t('productDevices.devices.errors.roleRequired')
    }
    if (lacksSignalMeaning(form)) return t('productDevices.devices.errors.signalMeaningRequired')
    if (preview.value?.invalid_characters.length) {
      return t('productDevices.devices.errors.invalidCharacters', {
        characters: preview.value.invalid_characters.join(' '),
      })
    }
    return null
  },
  save: async (form, isEdit, device) => {
    const body = deviceSaveRequest(form, kind.value)
    if (!body) throw new Error('incomplete form')
    if (isEdit && device) return await updateProductDevice(device.id, device.edit_version, body)
    const created = await createProductDevice(props.productId, body)
    // Images picked before the device existed are uploaded now that it has an id.
    await imagesSection.value?.flushPendingUploads(created.id)
    return created
  },
  onSaved: (saved) => emit('saved', saved),
  unknownErrorMessage: t('productDevices.devices.errors.unknown'),
})

watch(visible, (open) => {
  if (open) void resources.load()
})

// ── Choices ───────────────────────────────────────────────────────────

function optionChoices(
  category: 'driving_medium' | 'energy_behaviour',
  currentId: number | null,
): { value: number; label: string }[] {
  return resources
    .optionsOf(category, true)
    .filter((option) => !option.archived || option.id === currentId)
    .map((option) => ({
      value: option.id,
      label:
        category === 'driving_medium'
          ? `${localize(option.label)} (${option.letter})`
          : localize(option.label),
    }))
}

const mediumChoices = computed(() => optionChoices('driving_medium', props.device?.driving_medium_id ?? null))
const lossChoices = computed(() =>
  optionChoices('energy_behaviour', props.device?.energy_loss_behaviour_id ?? null),
)
const restorationChoices = computed(() =>
  optionChoices('energy_behaviour', props.device?.energy_restoration_behaviour_id ?? null),
)
const kindChoices = computed(() =>
  resources.kinds
    .filter((k) => !k.archived || k.id === props.device?.kind_id)
    .map((k) => ({ value: k.id, label: localize(k.label) })),
)

const kind = computed(() =>
  form.kind_id === null ? undefined : resources.kindById.get(form.kind_id),
)
// ── Rename ────────────────────────────────────────────────────────────

const { ask } = useConfirmAsync()

/** Whether saving changes the name of a stored device. */
const renames = computed(() => {
  const device = props.device
  if (!device) return false
  return (
    form.location.trim() !== device.location ||
    form.name.trim() !== device.name ||
    form.driving_medium_id !== device.driving_medium_id ||
    (form.number !== null && form.number !== device.number)
  )
})

/** The plans a renamed device must be renamed in, after the machine's disciplines. */
const renamePlans = computed(() => {
  const d = props.disciplines
  return [
    ...(d?.electrics ? ['eplan', 'plcCode'] : []),
    ...(d?.pneumatics ? ['pneumatics'] : []),
    ...(d?.hydraulics ? ['hydraulics'] : []),
    ...(d?.robotics ? ['robotProgram'] : []),
    'cadAssembly',
  ].map((key) => t(`productDevices.devices.renamePlans.${key}`))
})

// The hosting page fills the calculations section, reporting what it loaded for the rename.
defineSlots<{ calculations?(props: { device: ProductDevice; onLoaded: typeof onCalculationsLoaded }): unknown }>()

/** The released calculations of the device, which keep its old name until their next revision. */
const releasedCalculations = ref<string[]>([])

function onCalculationsLoaded(calculations: Array<{ document_number: string; released_at: string | null }>): void {
  releasedCalculations.value = calculations.filter((c) => c.released_at).map((c) => c.document_number)
}

// Renaming a device reaches beyond Glados, so it asks first and names what has to follow.
async function submit(): Promise<void> {
  if (renames.value) {
    const calculations = releasedCalculations.value.length
      ? ` ${t('productDevices.devices.renameCalculations', { numbers: releasedCalculations.value.join(', ') })}`
      : ''
    const go = await ask({
      group: 'device-rename',
      header: t('productDevices.devices.renameTitle'),
      message: t('productDevices.devices.renameMessage', { plans: renamePlans.value.join(', ') }) + calculations,
      icon: 'mdi mdi-alert-outline',
      rejectProps: { label: t('common.cancel'), severity: 'secondary' },
      acceptProps: { label: t('productDevices.devices.renameAccept'), severity: 'warn' },
    })
    if (!go) return
  }
  await onSubmit()
}

/** The longest PLC tag of this name passes the limit of the product's PLC environment. */
const tagTooLong = computed(() => {
  const longest = preview.value?.longest_tag_length
  const max = preview.value?.max_tag_length
  return longest != null && max != null && longest > max
})

/** A device of a kind without driving medium, such as a button, has none and no letter in its name. */
const needsMedium = computed(() => !kind.value?.without_driving_medium)

const livePositions = computed(() =>
  (kind.value?.positions ?? []).filter(
    (p) => !p.archived || p.id === props.device?.initial_position_id,
  ),
)
const liveParameters = computed(() => (kind.value?.parameters ?? []).filter((p) => !p.archived))


function positionLabel(positionId: number): string {
  const own = form.position_labels[String(positionId)]
  const position = kind.value?.positions.find((p) => p.id === positionId)
  const base = position ? localize(position.label) : ''
  return own ? `${own} (${base})` : base
}

const positionChoices = computed(() =>
  livePositions.value.map((p) => ({ value: p.id, label: positionLabel(p.id) })),
)
const initialPosition = computed(() =>
  livePositions.value.find((p) => p.id === form.initial_position_id),
)

function numberParameter(id: number): number | null {
  const value = form.parameters[String(id)]
  return typeof value === 'number' ? value : null
}

function textParameter(id: number): string {
  const value = form.parameters[String(id)]
  return typeof value === 'string' ? value : ''
}

function onKindChange(): void {
  resetKindSpecificFields(form)
}

// ── Name preview ──────────────────────────────────────────────────────

const preview = ref<ProductDeviceNamePreview | null>(null)
const imagesSection = ref<InstanceType<typeof ProductDeviceImagesSection> | null>(null)
const host = useHostStore()
let previewSeq = 0

const refreshPreview = useDebounceFn(async () => {
  const seq = ++previewSeq
  if ((needsMedium.value && form.driving_medium_id === null) || !form.name.trim()) {
    preview.value = null
    return
  }
  try {
    const result = await previewProductDeviceName(props.productId, {
      location: form.location,
      name: form.name,
      driving_medium_id: needsMedium.value ? form.driving_medium_id : null,
      number: form.number,
      device_id: props.device?.id ?? null,
      kind_id: form.kind_id,
    })
    if (seq === previewSeq) preview.value = result
  } catch {
    if (seq === previewSeq) preview.value = null
  }
}, 300)

watch(
  () => [visible.value, form.location, form.name, form.driving_medium_id, form.number, form.kind_id] as const,
  ([open]) => {
    if (open) void refreshPreview()
    else preview.value = null
  },
)

const header = computed(() => {
  if (props.readonly) return props.device?.name_utf8 ?? ''
  return isEditMode.value
    ? t('productDevices.devices.editDevice')
    : t('productDevices.devices.createDevice')
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="header"
    :style="{ width: 'var(--dialog-width-lg)' }"
    :pt="{ content: { 'data-testid': 'product-device-dialog' } }"
  >
    <form class="device-form" @submit.prevent="submit">
      <Message v-if="sequenceCoverage === 'none'" severity="warn" data-testid="device-not-in-sequence">
        {{ t('productDevices.completeness.notInSequence') }}
      </Message>
      <fieldset class="dialog-section" :disabled="readonly">
        <legend>{{ t('productDevices.devices.sections.name') }}</legend>
        <div class="grid name-grid">
          <div class="field">
            <label for="pd-location">{{ t('productDevices.devices.fields.location') }}</label>
            <InputText id="pd-location" v-model="form.location" :maxlength="60" autocomplete="off" fluid />
          </div>
          <div class="field">
            <label for="pd-name">{{ t('productDevices.devices.fields.name') }} *</label>
            <InputText
              id="pd-name"
              v-model="form.name"
              :maxlength="120"
              autocomplete="off"
              aria-required="true"
              fluid
            />
          </div>
          <div v-if="needsMedium" class="field">
            <label id="pd-medium-label" for="pd-medium">{{ t('productDevices.devices.fields.drivingMedium') }} *</label>
            <Select
              v-model="form.driving_medium_id"
              input-id="pd-medium"
              aria-labelledby="pd-medium-label"
              :options="mediumChoices"
              option-label="label"
              option-value="value"
              :disabled="readonly"
              :empty-message="t('productDevices.devices.emptyList')"
              fluid
            />
          </div>
          <div class="field">
            <label for="pd-number">{{ t('productDevices.devices.fields.number') }}</label>
            <InputNumber
              v-model="form.number"
              input-id="pd-number"
              :min="1"
              :use-grouping="false"
              :placeholder="t('productDevices.devices.fields.numberAuto')"
              :disabled="readonly"
              fluid
            />
          </div>
        </div>
        <div class="name-preview" data-testid="device-name-preview">
          <template v-if="!preview || preview.invalid_characters.length === 0">
            <div>
              <span class="preview-label">UTF-8</span>
              <code>{{ preview?.full_name_utf8 || getEmptyPlaceholder() }}</code>
            </div>
            <div>
              <span class="preview-label">ASCII</span>
              <code>{{ preview?.full_name_ascii || getEmptyPlaceholder() }}</code>
            </div>
            <Message v-if="preview?.taken" severity="warn" size="small">
              {{ t('productDevices.devices.nameTaken') }}
            </Message>
            <Message v-if="tagTooLong" severity="warn" size="small" data-testid="device-tag-too-long">
              {{
                t('productDevices.devices.tagTooLong', {
                  length: preview?.longest_tag_length,
                  max: preview?.max_tag_length,
                })
              }}
            </Message>
          </template>
          <Message v-else severity="error" size="small">
            {{
              t('productDevices.devices.errors.invalidCharacters', {
                characters: preview.invalid_characters.join(' '),
              })
            }}
          </Message>
        </div>
      </fieldset>

      <fieldset class="dialog-section" :disabled="readonly">
        <legend>{{ t('productDevices.devices.sections.device') }}</legend>
        <div class="grid">
          <div class="field">
            <label id="pd-kind-label" for="pd-kind">{{ t('productDevices.devices.fields.kind') }} *</label>
            <Select
              v-model="form.kind_id"
              input-id="pd-kind"
              aria-labelledby="pd-kind-label"
              :options="kindChoices"
              option-label="label"
              option-value="value"
              :disabled="readonly"
              :empty-message="t('productDevices.devices.emptyList')"
              fluid
              @change="onKindChange"
            />
          </div>
          <div class="field">
            <label class="checkbox-label">
              <Checkbox v-model="form.safety_relevant" binary input-id="pd-safety" :disabled="readonly" />
              <span>{{ t('productDevices.devices.fields.safetyRelevant') }}</span>
            </label>
          </div>
          <div class="field field-wide">
            <label for="pd-description">{{ t('productDevices.devices.fields.description') }}</label>
            <Textarea id="pd-description" v-model="form.description" rows="2" auto-resize fluid />
          </div>
        </div>
      </fieldset>

      <fieldset v-if="kind" class="dialog-section" :disabled="readonly">
        <legend>{{ t('productDevices.devices.sections.plc') }}</legend>
        <div class="grid">
          <div class="field">
            <label id="pd-initial-label" for="pd-initial">{{ t('productDevices.devices.fields.initialPosition') }}</label>
            <Select
              v-model="form.initial_position_id"
              input-id="pd-initial"
              aria-labelledby="pd-initial-label"
              :options="positionChoices"
              option-label="label"
              option-value="value"
              show-clear
              :disabled="readonly"
              fluid
            />
          </div>
          <div v-if="initialPosition?.takes_value" class="field">
            <label for="pd-initial-value">
              {{ t('productDevices.devices.fields.initialPositionValue') }}
              <span v-if="initialPosition.unit">({{ initialPosition.unit }})</span>
            </label>
            <InputNumber
              v-model="form.initial_position_value"
              input-id="pd-initial-value"
              :max-fraction-digits="3"
              :disabled="readonly"
              fluid
            />
          </div>
          <div class="field">
            <label id="pd-loss-label" for="pd-loss">{{ t('productDevices.devices.fields.energyLoss') }}</label>
            <Select
              v-model="form.energy_loss_behaviour_id"
              input-id="pd-loss"
              aria-labelledby="pd-loss-label"
              :options="lossChoices"
              option-label="label"
              option-value="value"
              show-clear
              :disabled="readonly"
              fluid
            />
          </div>
          <div class="field">
            <label id="pd-restoration-label" for="pd-restoration">{{ t('productDevices.devices.fields.energyRestoration') }}</label>
            <Select
              v-model="form.energy_restoration_behaviour_id"
              input-id="pd-restoration"
              aria-labelledby="pd-restoration-label"
              :options="restorationChoices"
              option-label="label"
              option-value="value"
              show-clear
              :disabled="readonly"
              fluid
            />
          </div>
          <div class="field">
            <label for="pd-monitoring">{{ t('productDevices.devices.fields.monitoringTime') }}</label>
            <InputNumber
              v-model="form.monitoring_time_ms"
              input-id="pd-monitoring"
              :min="0"
              suffix=" ms"
              :disabled="readonly"
              fluid
            />
          </div>
          <ProductDeviceDrivenBy
            v-model:driven-by-id="form.driven_by_id"
            v-model:position-map="form.driven_position_map"
            :device="device"
            :devices="devices ?? []"
            :kind-id="form.kind_id"
            :positions="livePositions"
            :readonly="readonly"
          />
        </div>

        <div v-if="livePositions.length" class="sub-section">
          <h4>{{ t('productDevices.devices.positionLabels') }}</h4>
          <p class="hint">{{ t('productDevices.devices.positionLabelsHint') }}</p>
          <div class="grid">
            <div v-for="position in livePositions" :key="position.id" class="field">
              <label :for="`pd-poslabel-${position.id}`">{{ localize(position.label) }}</label>
              <InputText
                :id="`pd-poslabel-${position.id}`"
                v-model="form.position_labels[String(position.id)]"
                :maxlength="60"
                fluid
              />
            </div>
          </div>
        </div>

        <div v-if="livePositions.length && !form.driven_by_id" class="sub-section">
          <h4>{{ t('productDevices.devices.travelTimes') }}</h4>
          <p class="hint">{{ t('productDevices.devices.travelTimesHint') }}</p>
          <div class="grid">
            <div v-for="position in livePositions" :key="position.id" class="field">
              <label :for="`pd-travel-${position.id}`">{{ positionLabel(position.id) }}</label>
              <InputNumber
                v-model="form.travel_times_ms[String(position.id)]"
                :input-id="`pd-travel-${position.id}`"
                :min="0"
                :max="3600000"
                suffix=" ms"
                :disabled="readonly"
                fluid
              />
            </div>
          </div>
        </div>

        <div v-if="liveParameters.length" class="sub-section">
          <h4>{{ t('productDevices.devices.parameters') }}</h4>
          <div class="grid">
            <div v-for="parameter in liveParameters" :key="parameter.id" class="field">
              <label :for="`pd-param-${parameter.id}`">
                {{ localize(parameter.label) }}
                <span v-if="parameter.unit">({{ parameter.unit }})</span>
              </label>
              <InputNumber
                v-if="parameter.value_type === 'number'"
                :model-value="numberParameter(parameter.id)"
                :input-id="`pd-param-${parameter.id}`"
                :max-fraction-digits="3"
                :disabled="readonly"
                fluid
                @update:model-value="form.parameters[String(parameter.id)] = $event"
              />
              <Checkbox
                v-else-if="parameter.value_type === 'boolean'"
                :model-value="form.parameters[String(parameter.id)] === true"
                :input-id="`pd-param-${parameter.id}`"
                binary
                :disabled="readonly"
                @update:model-value="form.parameters[String(parameter.id)] = $event"
              />
              <InputText
                v-else
                :id="`pd-param-${parameter.id}`"
                :model-value="textParameter(parameter.id)"
                :maxlength="200"
                fluid
                @update:model-value="form.parameters[String(parameter.id)] = $event ?? ''"
              />
            </div>
          </div>
        </div>
      </fieldset>

      <ProductDeviceImagesSection
        v-if="host.storageEnabled"
        ref="imagesSection"
        :product-id="productId"
        :device-id="device?.id ?? null"
        :can-edit="!readonly"
      />

      <ProductDeviceComponentsEditor
        v-model="form.components"
        :kind="kind"
        :disabled="readonly"
        :safety-relevant="form.safety_relevant"
      />

      <slot v-if="device" name="calculations" :device="device" :on-loaded="onCalculationsLoaded" />
    </form>

    <template #footer>
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error">{{ errorMessage }}</Message>
      <Button
        type="button"
        :label="readonly ? t('common.close') : t('common.cancel')"
        severity="secondary"
        text
        :disabled="submitting"
        @click="onCancel"
      />
      <Button
        v-if="!readonly"
        :label="t('common.save')"
        icon="mdi mdi-content-save-outline"
        :loading="submitting"
        @click="submit"
      />
    </template>
  </Dialog>
  <ConfirmDialog group="device-rename" />
</template>

<style scoped lang="scss">
// The error sits left of the buttons, so it shows however far the form is scrolled.
.footer-error {
  flex: 1 1 auto;
  align-self: center;
}

.device-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2) var(--space-4);
}

.name-grid {
  grid-template-columns: 1fr 2fr 1fr 8rem;
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
  margin-top: var(--space-5);
}

.name-preview {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--p-border-radius-sm);
  background: var(--p-content-hover-background);

  code {
    font-size: var(--font-size-md);
  }
}

.preview-label {
  display: inline-block;
  width: 3.5rem;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.sub-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-top: var(--space-2);

  h4 {
    margin: 0;
    font-size: var(--font-size-sm);
    font-weight: 600;
  }
}

.hint {
  margin: 0;
}
</style>
