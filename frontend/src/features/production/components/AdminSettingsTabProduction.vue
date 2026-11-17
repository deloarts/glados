<script setup lang="ts">
import { computed, onMounted, reactive, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { AdminSettingsTabShell, useAdminSettingsStore, useSettingsSave } from '@/features/admin-settings'
import { useInspectionMethodsStore } from '@/features/inspection-methods'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const store = useAdminSettingsStore()
const inspectionMethodsStore = useInspectionMethodsStore()
const { hasPermission } = usePermissions()

// Referencing an already-archived inspection method as the default is
// allowed: every method stays selectable, archived ones sorted after live
// ones and tagged (see useArchivableOptions.ts).
const { sortedOptions: inspectionMethodOptions, isArchived: isInspectionMethodArchived } =
  useArchivableOptions(computed(() => inspectionMethodsStore.items))
const selectedInspectionMethod = computed(
  () =>
    inspectionMethodOptions.value.find((m) => m.id === form.default_inspection_method_id) ?? null,
)

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

onMounted(() => {
  if (inspectionMethodsStore.items.length === 0) {
    void inspectionMethodsStore.refresh()
  }
})

interface ProductionForm {
  default_external_lead_days: number
  response_time_days: number
  frozen_window_hours: number
  require_qa: boolean
  default_inspection_method_id: number | null
  require_source_item_approval: boolean
  assign_approved_material_to_item: boolean
  overwrite_item_material_on_approval: boolean
  over_delivery_tolerance_percent: number
  under_delivery_tolerance_percent: number
}

const form = reactive<ProductionForm>({
  default_external_lead_days: 0,
  response_time_days: 1,
  frozen_window_hours: 0,
  require_qa: false,
  default_inspection_method_id: null,
  require_source_item_approval: false,
  assign_approved_material_to_item: false,
  overwrite_item_material_on_approval: false,
  over_delivery_tolerance_percent: 0,
  under_delivery_tolerance_percent: 0,
})

watch(
  () => store.settings?.production,
  (s) => {
    if (!s) return
    form.default_external_lead_days = s.default_external_lead_days
    form.response_time_days = s.response_time_days
    form.frozen_window_hours = s.frozen_window_hours
    form.require_qa = s.require_qa
    form.default_inspection_method_id = s.default_inspection_method_id
    form.require_source_item_approval = s.require_source_item_approval
    form.assign_approved_material_to_item = s.assign_approved_material_to_item
    form.overwrite_item_material_on_approval = s.overwrite_item_material_on_approval
  },
  { immediate: true },
)

// The delivery tolerances live on the order settings, which this tab saves
// alongside the production settings.
watch(
  () => store.settings?.orders,
  (s) => {
    if (!s) return
    form.over_delivery_tolerance_percent = s.over_delivery_tolerance_percent
    form.under_delivery_tolerance_percent = s.under_delivery_tolerance_percent
  },
  { immediate: true },
)

const { saving, onSave } = useSettingsSave(async () => {
  await store.saveProduction({
    default_external_lead_days: form.default_external_lead_days,
    response_time_days: form.response_time_days,
    frozen_window_hours: form.frozen_window_hours,
    require_qa: form.require_qa,
    default_inspection_method_id: form.default_inspection_method_id,
    require_source_item_approval: form.require_source_item_approval,
    assign_approved_material_to_item: form.assign_approved_material_to_item,
    overwrite_item_material_on_approval: form.overwrite_item_material_on_approval,
  })
  // Only once the order settings were read, so a failed read never resets
  // the tolerances to the form's defaults.
  if (!store.settings?.orders) return
  await store.saveOrders({
    over_delivery_tolerance_percent: form.over_delivery_tolerance_percent,
    under_delivery_tolerance_percent: form.under_delivery_tolerance_percent,
  })
})
</script>

<template>
  <AdminSettingsTabShell>
    <template #controls>
      <Toolbar>
        <template #start>
          <Button
            :label="t('common.save')"
            icon="mdi mdi-content-save"
            text
            severity="contrast"
            :loading="saving"
            :disabled="!canWrite"
            @click="onSave"
          />
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <p class="section-label">{{ t('adminSettings.production.scheduling') }}</p>

      <div class="field-row">
        <label :for="`${uid}-external-lead-days`">
          {{ t('adminSettings.production.externalLeadDays') }}
          <span class="hint">{{ t('adminSettings.production.externalLeadDaysHint') }}</span>
        </label>
        <InputNumber
          v-model="form.default_external_lead_days"
          :input-id="`${uid}-external-lead-days`"
          :disabled="!canWrite"
          :min="0"
          :use-grouping="false"
        />
      </div>

      <div class="field-row">
        <label :for="`${uid}-response-time-days`">
          {{ t('adminSettings.production.responseTimeDays') }}
          <span class="hint">{{ t('adminSettings.production.responseTimeDaysHint') }}</span>
        </label>
        <InputNumber
          v-model="form.response_time_days"
          :input-id="`${uid}-response-time-days`"
          :disabled="!canWrite"
          :min="0"
          :use-grouping="false"
        />
      </div>

      <div class="field-row">
        <label :for="`${uid}-frozen-window-hours`">
          {{ t('adminSettings.production.frozenWindowHours') }}
          <span class="hint">{{ t('adminSettings.production.frozenWindowHoursHint') }}</span>
        </label>
        <InputNumber
          v-model="form.frozen_window_hours"
          :input-id="`${uid}-frozen-window-hours`"
          :disabled="!canWrite"
          :min="0"
          :max="744"
          :use-grouping="false"
        />
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.production.qualitySection') }}</p>

      <div class="field-row field-row--toggle">
        <label :for="`${uid}-require-qa`">{{ t('adminSettings.production.requireQa') }}</label>
        <ToggleSwitch v-model="form.require_qa" :input-id="`${uid}-require-qa`" :disabled="!canWrite" />
        <small class="hint">{{ t('adminSettings.production.requireQaHint') }}</small>
      </div>

      <div class="field-row">
        <label :id="`${uid}-default-inspection-method-label`" :for="`${uid}-default-inspection-method`">
          {{ t('adminSettings.production.defaultInspectionMethod') }}
          <span class="hint">{{ t('adminSettings.production.defaultInspectionMethodHint') }}</span>
        </label>
        <Select
          v-model="form.default_inspection_method_id"
          :input-id="`${uid}-default-inspection-method`"
          :aria-labelledby="`${uid}-default-inspection-method-label`"
          :options="inspectionMethodOptions"
          :option-label="labelName"
          option-value="id"
          :disabled="!canWrite"
          :placeholder="t('adminSettings.production.defaultInspectionMethodPlaceholder')"
          fluid
        >
          <template #option="{ option }">
            <span>{{ localizeLabel(option.name) }}</span>
            <ArchivedOptionTag v-if="option.archived" />
          </template>
          <template #value="{ value }">
            <span v-if="value !== null">{{ localizeLabel(selectedInspectionMethod?.name) }}</span>
            <ArchivedOptionTag v-if="selectedInspectionMethod?.archived" />
          </template>
        </Select>
        <ArchivedSelectionWarning v-if="isInspectionMethodArchived(selectedInspectionMethod)" />
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.production.materialApprovalSection') }}</p>

      <div class="field-row field-row--toggle">
        <label :for="`${uid}-require-source-item-approval`">
          {{ t('adminSettings.production.requireSourceItemApproval') }}
        </label>
        <ToggleSwitch
          v-model="form.require_source_item_approval"
          :input-id="`${uid}-require-source-item-approval`"
          :disabled="!canWrite"
        />
        <small class="hint">{{ t('adminSettings.production.requireSourceItemApprovalHint') }}</small>
      </div>

      <div class="field-row field-row--toggle">
        <label :for="`${uid}-assign-approved-material-to-item`">
          {{ t('adminSettings.production.assignApprovedMaterialToItem') }}
        </label>
        <ToggleSwitch
          v-model="form.assign_approved_material_to_item"
          :input-id="`${uid}-assign-approved-material-to-item`"
          :disabled="!canWrite"
        />
        <small class="hint">{{ t('adminSettings.production.assignApprovedMaterialToItemHint') }}</small>
      </div>

      <div class="field-row field-row--toggle">
        <label :for="`${uid}-overwrite-item-material-on-approval`">
          {{ t('adminSettings.production.overwriteItemMaterialOnApproval') }}
        </label>
        <ToggleSwitch
          v-model="form.overwrite_item_material_on_approval"
          :input-id="`${uid}-overwrite-item-material-on-approval`"
          :disabled="!canWrite || !form.assign_approved_material_to_item"
        />
        <small class="hint">{{ t('adminSettings.production.overwriteItemMaterialOnApprovalHint') }}</small>
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.production.deliveriesSection') }}</p>

      <div class="field-row">
        <label :for="`${uid}-over-delivery-tolerance`">
          {{ t('adminSettings.production.overDeliveryTolerance') }}
          <span class="hint">{{ t('adminSettings.production.overDeliveryToleranceHint') }}</span>
        </label>
        <InputNumber
          v-model="form.over_delivery_tolerance_percent"
          :input-id="`${uid}-over-delivery-tolerance`"
          :disabled="!canWrite"
          :min="0"
          :max="100"
          :max-fraction-digits="2"
          suffix=" %"
          :use-grouping="false"
        />
      </div>

      <div class="field-row">
        <label :for="`${uid}-under-delivery-tolerance`">
          {{ t('adminSettings.production.underDeliveryTolerance') }}
          <span class="hint">{{ t('adminSettings.production.underDeliveryToleranceHint') }}</span>
        </label>
        <InputNumber
          v-model="form.under_delivery_tolerance_percent"
          :input-id="`${uid}-under-delivery-tolerance`"
          :disabled="!canWrite"
          :min="0"
          :max="100"
          :max-fraction-digits="2"
          suffix=" %"
          :use-grouping="false"
        />
      </div>
    </div>
  </AdminSettingsTabShell>
</template>
