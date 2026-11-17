<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { getBoughtItems } from '@/features/bought-items'
import { usePrintersStore } from '../stores/printersStore'
import { useEntityFormDialog } from '@/shared/composables/useEntityFormDialog'
import LookupMultiSelect from '@/shared/components/forms/LookupMultiSelect.vue'

import type { BoughtItemResponse } from '@/features/bought-items'
import type { LookupOption } from '@/shared/components/forms/lookupMultiSelect'
import type { PrinterKind, PrinterTransport } from '../types/printerRequest'
import type { PrinterResponse } from '../types/printerResponse'

interface Props {
  printer?: PrinterResponse | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [printer: PrinterResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const store = usePrintersStore()

const kindOptions = computed(() => [
  { label: t('printers.kinds.zpl_label'), value: 'zpl_label' as PrinterKind },
  { label: t('printers.kinds.ipp_document'), value: 'ipp_document' as PrinterKind },
])

const transportOptions = computed(() => [
  { label: t('printers.transports.raw'), value: 'raw' as PrinterTransport },
  { label: t('printers.transports.ipp'), value: 'ipp' as PrinterTransport },
])

interface FormState {
  name: string
  internal_name: string
  kind: PrinterKind
  host: string
  port: number
  timeout_seconds: number
  transport: PrinterTransport
  ipp_uri_path: string
  head_dpi: number | null
  format_convert_factor: number | null
  default_media: string
  location: string
  vendor: string
  model: string
  firmware: string
  bought_item_ids: number[]
  enabled: boolean
  is_default: boolean
  note: string
}

function createEmptyForm(): FormState {
  return {
    name: '',
    internal_name: '',
    kind: 'zpl_label',
    host: '',
    port: 9100,
    timeout_seconds: 5,
    transport: 'raw',
    ipp_uri_path: '/',
    head_dpi: 300,
    format_convert_factor: 2,
    default_media: '',
    location: '',
    vendor: '',
    model: '',
    firmware: '',
    bought_item_ids: [],
    enabled: true,
    is_default: false,
    note: '',
  }
}

function formFromPrinter(printer: PrinterResponse): FormState {
  return {
    name: printer.name,
    internal_name: printer.internal_name ?? '',
    kind: printer.kind,
    host: printer.host,
    port: printer.port,
    timeout_seconds: printer.timeout_seconds,
    transport: printer.transport,
    ipp_uri_path: printer.ipp_uri_path,
    head_dpi: printer.head_dpi,
    format_convert_factor: printer.format_convert_factor,
    default_media: printer.default_media ?? '',
    location: printer.location ?? '',
    vendor: printer.vendor ?? '',
    model: printer.model ?? '',
    firmware: printer.firmware ?? '',
    bought_item_ids: [...printer.bought_item_ids],
    enabled: printer.enabled,
    is_default: printer.is_default,
    note: printer.note ?? '',
  }
}

// The bought items are searched on the server as the user types, a page at
// a time, since the catalogue is too long to load whole.
const BOUGHT_ITEM_OPTIONS_LIMIT = 50

function toBoughtItemOption(item: BoughtItemResponse): LookupOption {
  return { id: item.id, label: item.article_name, sublabel: item.order_code_1 ?? undefined }
}

async function fetchBoughtItemOptions(query: string): Promise<LookupOption[]> {
  const page = await getBoughtItems({
    search: query || undefined,
    limit: BOUGHT_ITEM_OPTIONS_LIMIT,
  })
  return page.items.map(toBoughtItemOption)
}

// Labels the items a saved printer already names, archived ones included,
// since they need not be on the first page.
async function fetchBoughtItemsByIds(ids: number[]): Promise<LookupOption[]> {
  const pages = await Promise.all(
    ids.map((id) => getBoughtItems({ id, include_archived: true, limit: 1 })),
  )
  return pages.flatMap((page) => page.items.map(toBoughtItemOption))
}

const { form, submitting, errorMessage, isEditMode, onSubmit, onCancel } = useEntityFormDialog<
  PrinterResponse,
  FormState
>({
  visible,
  entity: () => props.printer,
  emptyForm: createEmptyForm,
  formFromEntity: formFromPrinter,
  validate: (form) =>
    form.name.trim() && form.host.trim() && form.port > 0 ? null : t('printers.errors.required'),
  save: (form, isEditMode, printer) => {
    const payload = {
      name: form.name.trim(),
      internal_name: form.internal_name.trim() || null,
      kind: form.kind,
      host: form.host.trim(),
      port: form.port,
      timeout_seconds: form.timeout_seconds,
      transport: form.transport,
      ipp_uri_path: form.ipp_uri_path.trim() || '/',
      head_dpi: form.kind === 'zpl_label' ? form.head_dpi : null,
      format_convert_factor: form.kind === 'zpl_label' ? form.format_convert_factor : null,
      default_media: form.kind === 'ipp_document' ? form.default_media.trim() || null : null,
      location: form.location.trim() || null,
      vendor: form.vendor.trim() || null,
      model: form.model.trim() || null,
      firmware: form.firmware.trim() || null,
      bought_item_ids: form.bought_item_ids,
      enabled: form.enabled,
      is_default: form.is_default,
      note: form.note.trim() || null,
    }
    return isEditMode && printer ? store.update(printer.id, payload) : store.create(payload)
  },
  onSaved: (saved) => emit('saved', saved),
  unknownErrorMessage: t('printers.errors.unknown'),
})

// Switching kind resets the other kind's fields, so no stale values stay
// attached.
watch(
  () => form.kind,
  (kind) => {
    // A port still at the other kind's default follows the kind; a port
    // set by hand stays.
    if (kind === 'zpl_label') {
      form.transport = 'raw'
      form.port = !form.port || form.port === 631 ? 9100 : form.port
      form.head_dpi = form.head_dpi ?? 300
      form.format_convert_factor = form.format_convert_factor ?? 1
    } else {
      form.transport = 'ipp'
      form.port = !form.port || form.port === 9100 ? 631 : form.port
      form.head_dpi = null
      form.format_convert_factor = null
    }
  },
)
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="isEditMode ? t('printers.create.editTitle') : t('printers.create.createTitle')"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <form class="printer-form" @submit.prevent="onSubmit">
      <div class="form-fields">
        <div class="field field-wide">
          <label for="p-name">{{ t('printers.create.fields.name') }} *</label>
          <InputText id="p-name" v-model="form.name" fluid autocomplete="off" />
        </div>

        <div class="field">
          <label for="p-internal-name">{{ t('printers.create.fields.internalName') }}</label>
          <InputText id="p-internal-name" v-model="form.internal_name" fluid autocomplete="off" />
        </div>

        <div class="field">
          <label id="p-kind-label" for="p-kind">{{ t('printers.create.fields.kind') }} *</label>
          <Select
            id="p-kind"
            aria-labelledby="p-kind-label"
            v-model="form.kind"
            :options="kindOptions"
            option-label="label"
            option-value="value"
            fluid
          />
        </div>

        <div class="field">
          <label for="p-host">{{ t('printers.create.fields.host') }} *</label>
          <InputText id="p-host" v-model="form.host" fluid autocomplete="off" />
        </div>

        <div class="field">
          <label for="p-port">{{ t('printers.create.fields.port') }} *</label>
          <InputNumber id="p-port" v-model="form.port" :min="1" :max="65535" :use-grouping="false" fluid />
        </div>

        <div class="field">
          <label id="p-transport-label" for="p-transport">{{ t('printers.create.fields.transport') }}</label>
          <Select
            id="p-transport"
            aria-labelledby="p-transport-label"
            v-model="form.transport"
            :options="transportOptions"
            option-label="label"
            option-value="value"
            fluid
          />
        </div>

        <div class="field">
          <label for="p-timeout">{{ t('printers.create.fields.timeoutSeconds') }}</label>
          <InputNumber
            id="p-timeout"
            v-model="form.timeout_seconds"
            :min="0.1"
            :max-fraction-digits="1"
            fluid
          />
        </div>

        <!-- ZPL-specific -->
        <template v-if="form.kind === 'zpl_label'">
          <div class="field">
            <label for="p-head-dpi">{{ t('printers.create.fields.headDpi') }}</label>
            <InputNumber id="p-head-dpi" v-model="form.head_dpi" :use-grouping="false" fluid />
          </div>
          <div class="field">
            <label for="p-format-convert">{{
              t('printers.create.fields.formatConvertFactor')
            }}</label>
            <InputNumber
              id="p-format-convert"
              v-model="form.format_convert_factor"
              :min="1"
              :use-grouping="false"
              fluid
              v-tooltip.top="t('printers.create.fields.formatConvertFactorHint')"
            />
          </div>
        </template>

        <!-- IPP-specific -->
        <template v-else>
          <div class="field">
            <label for="p-ipp-path">{{ t('printers.create.fields.ippUriPath') }}</label>
            <InputText
              id="p-ipp-path"
              v-model="form.ipp_uri_path"
              fluid
              v-tooltip.top="t('printers.create.fields.ippUriPathHint')"
            />
          </div>
          <div class="field">
            <label for="p-media">{{ t('printers.create.fields.defaultMedia') }}</label>
            <InputText id="p-media" v-model="form.default_media" fluid autocomplete="off" />
          </div>
        </template>

        <div class="field">
          <label for="p-location">{{ t('printers.create.fields.location') }}</label>
          <InputText id="p-location" v-model="form.location" fluid autocomplete="off" />
        </div>
        <div class="field">
          <label for="p-vendor">{{ t('printers.create.fields.vendor') }}</label>
          <InputText id="p-vendor" v-model="form.vendor" fluid autocomplete="off" />
        </div>
        <div class="field">
          <label for="p-model">{{ t('printers.create.fields.model') }}</label>
          <InputText id="p-model" v-model="form.model" fluid autocomplete="off" />
        </div>
        <div class="field">
          <label for="p-firmware">{{ t('printers.create.fields.firmware') }}</label>
          <InputText id="p-firmware" v-model="form.firmware" fluid autocomplete="off" />
        </div>

        <div class="field field-wide">
          <label id="p-bought-items-label" for="p-bought-items">{{ t('printers.create.fields.boughtItems') }}</label>
          <LookupMultiSelect
            id="p-bought-items"
            aria-labelledby="p-bought-items-label"
            v-model="form.bought_item_ids"
            :fetch="fetchBoughtItemOptions"
            :fetch-by-ids="fetchBoughtItemsByIds"
            :placeholder="t('printers.create.fields.boughtItemsPlaceholder')"
            :compact="false"
          />
        </div>

        <div class="field">
          <label for="p-enabled">{{ t('printers.create.fields.enabled') }}</label>
          <ToggleSwitch id="p-enabled" v-model="form.enabled" />
        </div>
        <div class="field">
          <label for="p-default">{{ t('printers.create.fields.isDefault') }}</label>
          <ToggleSwitch id="p-default" v-model="form.is_default" />
        </div>

        <div class="field field-wide">
          <label for="p-note">{{ t('printers.create.fields.note') }}</label>
          <Textarea id="p-note" v-model="form.note" rows="2" fluid auto-resize />
        </div>
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
.printer-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
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
