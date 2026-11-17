<script setup lang="ts">
// The shop-floor page for one machine, kept open all shift. This view owns
// the bars; MachineDetailContent owns the data and exposes what the bars
// need through a template ref.
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { hasAction } from '@/core/utils/lifecycleActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import { HelpButton } from '@/shared/help'
import MachineDetailContent from '../components/MachineDetailContent.vue'
import { useProductionOrderCancel } from '@/features/production/queue'
import { usePageTitle } from '@/core/composables/usePageTitle'
import { MachineDowntimesDialog } from '@/features/production-machines'
import { formatISODateTime } from '@/core/utils/dates'

import type { MenuItem } from 'openvue/menuitem'
import LabelTag from '@/shared/components/labels/LabelTag.vue'

const route = useRoute()
const { t } = useI18n()

const showDowntimesDialog = ref(false)

const machineId = computed(() => Number(route.params.id))

const content = ref<InstanceType<typeof MachineDetailContent> | null>(null)

const machine = computed(() => content.value?.machine ?? null)
const ready = computed(() => content.value?.ready ?? false)
const pools = computed(() => content.value?.pools ?? [])
const machineState = computed(() => content.value?.machineState ?? 'idle')
const machineStateTagSeverity = computed(() => content.value?.machineStateTagSeverity ?? 'secondary')
const canWrite = computed(() => content.value?.canWrite ?? false)
const controlTarget = computed(() => content.value?.controlTarget ?? null)
const controlCanOperateInspection = computed(
  () => content.value?.controlCanOperateInspection ?? true,
)
const controlStartBlocked = computed(() => content.value?.controlStartBlocked ?? true)
// The control target's actions stay visible without the rights for them,
// disabled and naming the missing permission.
const { missing } = useMissingPermission()
const writeBlocked = computed(() =>
  canWrite.value ? '' : missing(Permission.WRITE_PRODUCTION_ORDERS),
)
const completeBlocked = computed(() => {
  if (writeBlocked.value) return writeBlocked.value
  return controlCanOperateInspection.value ? '' : t('productionQueue.card.inspectionPermissionTooltip')
})
// The most actionable reason first, a missing permission before the state.
const controlStartBlockedTooltip = computed(
  () => writeBlocked.value || content.value?.controlStartBlockedTooltip || '',
)
// Another user's order needs Manage Production Orders to cancel.
const { cancelBlocked } = useProductionOrderCancel()
const controlCancelBlocked = computed(() => {
  if (writeBlocked.value) return writeBlocked.value
  return controlTarget.value ? cancelBlocked(controlTarget.value) : ''
})
const canPrint = computed(() => content.value?.canPrint ?? false)
const printing = computed(() => content.value?.printing ?? null)
const controlCanOpenItem = computed(() => content.value?.controlCanOpenItem ?? false)
const controlCanOpenSourceItem = computed(() => content.value?.controlCanOpenSourceItem ?? false)

const pageHeading = computed(() =>
  machine.value ? machine.value.internal_name : t('main.sidebar.resources.machines'),
)
const { setPageTitle } = usePageTitle()
watch(pageHeading, setPageTitle, { immediate: true })

// The main Print button prints the docket; the dropdown adds the label.
const printMenuItems = computed<MenuItem[]>(() => [
  {
    label: t('productionQueue.card.printLabel'),
    icon: 'mdi mdi-tag-outline',
    command: () => content.value?.onPrint('production_order_label'),
  },
])
</script>

<template>
  <PageLayout>
    <template #info>
      <InfoBar>
        <template v-if="machine">
          <span class="machine-name">{{ machine.internal_name }}</span>
          <span class="info-sep" />
          <span class="info-muted">{{ machine.vendor }} {{ machine.model }}</span>
          <template v-if="machine.fabrication_methods.length">
            <span class="info-sep" />
            <LabelTag
              v-for="method in machine.fabrication_methods"
              :key="method.id"
              :label="method"
            />
          </template>
          <template v-if="pools.length">
            <span class="info-sep" />
            <Tag
              v-for="pool in pools"
              :key="pool.id"
              :value="pool.name"
              severity="info"
              icon="mdi mdi-view-grid-outline"
            />
          </template>
          <span class="info-sep" />
          <Tag
            :value="t(`production.machineDetail.state.${machineState}`)"
            :severity="machineStateTagSeverity"
          />
          <template v-if="machine.open_downtime">
            <span class="info-sep" />
            <Tag
              severity="danger"
              icon="mdi mdi-alert-octagon-outline"
              :value="
                t('productionMachines.downtime.badge', {
                  time: formatISODateTime(machine.open_downtime.started_at),
                })
              "
            />
          </template>
        </template>
        <template v-else-if="!ready">
          <Skeleton width="9rem" height="1.5rem" border-radius="1rem" />
          <Skeleton width="6rem" height="1.5rem" border-radius="1rem" />
        </template>
      </InfoBar>
    </template>

    <template #controls>
      <ControlsBar>
        <template #start>
          <template v-if="controlTarget">
            <!-- Each span carries the tooltip, since a disabled button shows
                 none of its own. -->
            <span
              v-if="controlTarget.status === 'queued' || controlTarget.status === 'paused'"
              v-tooltip.bottom="controlStartBlockedTooltip || undefined"
            >
              <Button
                :label="
                  t(
                    controlTarget.status === 'paused'
                      ? 'productionQueue.card.actions.resume'
                      : 'productionQueue.card.actions.start',
                  )
                "
                icon="mdi mdi-play"
                severity="contrast"
                text
                :disabled="!canWrite || controlStartBlocked"
                data-testid="machine-control-start"
                @click="content?.onCardStart(controlTarget)"
              />
            </span>
            <span v-if="hasAction(controlTarget, 'pause')" v-tooltip.bottom="writeBlocked || undefined">
              <Button
                :label="t('productionQueue.card.actions.pause')"
                icon="mdi mdi-pause"
                severity="contrast"
                text
                :disabled="!canWrite"
                @click="content?.onCardPause(controlTarget)"
              />
            </span>
            <span
              v-if="hasAction(controlTarget, 'record_completion')"
              v-tooltip.bottom="completeBlocked || undefined"
            >
              <Button
                :label="t('productionQueue.card.actions.complete')"
                icon="mdi mdi-check"
                severity="contrast"
                text
                :disabled="!canWrite || !controlCanOperateInspection"
                data-testid="machine-control-complete"
                @click="content?.onCardComplete(controlTarget)"
              />
            </span>
            <span v-if="hasAction(controlTarget, 'scrap')" v-tooltip.bottom="writeBlocked || undefined">
              <Button
                :label="t('productionQueue.card.actions.scrap')"
                icon="mdi mdi-delete-alert-outline"
                severity="contrast"
                text
                :disabled="!canWrite"
                @click="content?.onCardScrap(controlTarget)"
              />
            </span>
            <span
              v-if="hasAction(controlTarget, 'cancel')"
              v-tooltip.bottom="controlCancelBlocked || undefined"
            >
              <Button
                :label="t('productionQueue.card.actions.cancel')"
                icon="mdi mdi-close"
                severity="contrast"
                text
                :disabled="controlCancelBlocked !== ''"
                data-testid="machine-control-cancel"
                @click="content?.onCardCancel(controlTarget)"
              />
            </span>

            <Divider layout="vertical" />
          </template>

          <SplitButton
            :label="t('productionQueue.card.printDocket')"
            icon="mdi mdi-file-document-outline"
            severity="contrast"
            text
            :disabled="!controlTarget || !canPrint || printing !== null"
            :model="printMenuItems"
            @click="content?.onPrint('production_order_docket')"
          />

          <Divider layout="vertical" />

          <Button
            :label="t('production.machineDetail.controls.openItem')"
            icon="mdi mdi-cube-outline"
            severity="contrast"
            text
            :disabled="!controlCanOpenItem"
            @click="content?.openItemDialog()"
          />
          <Button
            :label="t('production.machineDetail.controls.openSourceMaterial')"
            icon="mdi mdi-package-variant-closed"
            severity="contrast"
            text
            :disabled="!controlCanOpenSourceItem"
            @click="content?.openSourceItemDialog()"
          />
          <Button
            :label="t('production.machineDetail.controls.openOrder')"
            icon="mdi mdi-clipboard-text-outline"
            severity="contrast"
            text
            :disabled="!controlTarget"
            @click="content?.openOrderDialog()"
          />

          <Divider layout="vertical" />

          <Button
            :label="t('productionMachines.downtime.button')"
            icon="mdi mdi-alert-octagon-outline"
            severity="contrast"
            text
            @click="showDowntimesDialog = true"
          />
        </template>
        <template #handbook>
          <HelpButton rounded />
        </template>
      </ControlsBar>
    </template>

    <MachineDetailContent ref="content" :machine-id="machineId" />
  </PageLayout>

  <MachineDowntimesDialog v-model:visible="showDowntimesDialog" :initial-machine-id="machineId" />
</template>

<style scoped lang="scss">
.machine-name {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.info-muted {
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}
</style>
