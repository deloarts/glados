<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import LotCreateDialog from './LotCreateDialog.vue'
import AutoPlanDialog from '../../components/AutoPlanDialog.vue'
import { useAutoPlanRunStore } from '../../stores/autoPlanRunStore'
import { useProductionLotsEditStore } from '../stores/productionLotsEditStore'
import { useProductionLotsFiltersStore } from '../stores/productionLotsFiltersStore'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import { HelpButton } from '@/shared/help'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'

const { t } = useI18n()
const { hasPermission } = usePermissions()
const editStore = useProductionLotsEditStore()
const filtersStore = useProductionLotsFiltersStore()
const autoPlanRunStore = useAutoPlanRunStore()

defineProps<{
  showManageOrders: boolean
  showManageQuotes: boolean
  showManageProduction: boolean
  showManageSource: boolean
}>()

const emit = defineEmits<{
  'toggle-manage-orders': []
  'toggle-manage-quotes': []
  'toggle-manage-production': []
  'toggle-manage-source': []
}>()

const canWrite = computed(() => hasPermission(Permission.WRITE_LOTS))
const canWriteOrders = computed(() => hasPermission(Permission.WRITE_ORDERS))
const { missing } = useMissingPermission()
const lotsBlocked = computed(() => missing(Permission.WRITE_LOTS))
const lotsAndOrdersBlocked = computed(() => missing(Permission.WRITE_LOTS, Permission.WRITE_ORDERS))
// Manage Production assigns positions to machines, which creates and moves
// production orders.
const productionBlocked = computed(() =>
  missing(Permission.WRITE_LOTS, Permission.WRITE_PRODUCTION_ORDERS),
)
const autoPlanBlocked = computed(() => missing(Permission.WRITE_PRODUCTION_ORDERS))
// A missing permission names itself; otherwise the coverage filter is the hint.
const productionHint = computed(
  () =>
    productionBlocked.value ||
    (filtersStore.coverageFilterArmed
      ? t('production.lots.controls.manageProductionFilterHint')
      : ''),
)

const showCreate = ref(false)
const showAutoPlan = ref(false)
</script>

<template>
  <ControlsBar>
    <template #start>
      <!-- Each span carries the tooltip, since a disabled button shows none
           of its own. -->
      <span v-tooltip="lotsBlocked || undefined">
        <Button
          :label="t('production.lots.controls.new')"
          icon="mdi mdi-plus"
          severity="contrast"
          text
          :disabled="!canWrite"
          data-testid="new-lot"
          @click="showCreate = true"
        />
      </span>
      <span v-tooltip="lotsBlocked || undefined">
        <Button
          :label="t('production.lots.controls.edit')"
          icon="mdi mdi-pencil"
          severity="contrast"
          :text="!editStore.editMode"
          :disabled="!canWrite"
          data-testid="edit-lots"
          @click="editStore.toggleEditMode()"
        />
      </span>
      <Divider layout="vertical" />
      <span v-tooltip="lotsAndOrdersBlocked || undefined">
        <Button
          :label="t('production.lots.controls.manageOrders')"
          icon="mdi mdi-truck-outline"
          severity="contrast"
          :text="!showManageOrders"
          :disabled="!(canWrite && canWriteOrders)"
          @click="emit('toggle-manage-orders')"
        />
      </span>
      <span v-tooltip="lotsAndOrdersBlocked || undefined">
        <Button
          :label="t('production.lots.controls.manageQuotes')"
          icon="mdi mdi-scale-balance"
          severity="contrast"
          :text="!showManageQuotes"
          :disabled="!(canWrite && canWriteOrders)"
          data-testid="manage-quotes"
          @click="emit('toggle-manage-quotes')"
        />
      </span>
      <span v-tooltip="productionHint || undefined">
        <Button
          :label="t('production.lots.controls.manageProduction')"
          icon="mdi mdi-robot-industrial-outline"
          severity="contrast"
          :text="!showManageProduction"
          :disabled="productionBlocked !== ''"
          data-testid="manage-production"
          @click="emit('toggle-manage-production')"
        />
      </span>
      <span v-tooltip="lotsBlocked || undefined">
        <Button
          :label="t('production.lots.controls.manageSource')"
          icon="mdi mdi-database-import-outline"
          severity="contrast"
          :text="!showManageSource"
          :disabled="!canWrite"
          @click="emit('toggle-manage-source')"
        />
      </span>
      <Divider layout="vertical" />
      <!-- anyRunActive covers a run started by anyone; status ===
           'running' additionally covers the moment right after THIS tab's
           own run() call, before the live-signal round trip has caught
           activeRun up to it. Without it the icon would lag a beat on the
           runner's own click. Same binding as ProductionCapacityControls. -->
      <span v-tooltip="autoPlanBlocked || undefined">
        <Button
          :label="t('productionSchedule.autoPlan.trigger')"
          severity="contrast"
          text
          :icon="
            autoPlanRunStore.anyRunActive || autoPlanRunStore.status === 'running'
              ? 'mdi mdi-loading mdi-spin'
              : 'mdi mdi-calendar-sync'
          "
          :disabled="autoPlanBlocked !== ''"
          data-testid="auto-plan"
          @click="showAutoPlan = true"
        />
      </span>
    </template>
    <template #handbook>
      <HelpButton rounded />
    </template>
  </ControlsBar>

  <LotCreateDialog v-model:visible="showCreate" />
  <AutoPlanDialog v-model:visible="showAutoPlan" />
</template>
