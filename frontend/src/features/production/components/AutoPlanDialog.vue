<script setup lang="ts">
// Auto-Plan dialog. Steps from the confirm form to the running view and the
// results, or to an observer view while someone else's run is active. The
// run itself lives in the run store, so a dialog opened mid-run attaches to it.
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { SseHttpError } from '@/core/realtime/sseClient'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { getMachinePools, getProductionMachines } from '@/features/production-machines'
import { useAdminSettingsStore } from '@/features/admin-settings'
import { HelpDrawer } from '@/shared/help'
import { AutoPlanConnectionLostError } from '../api/autoPlanScheduleStream'
import {
  AutoPlanAlreadyRunningError,
  AutoPlanRunTakenError,
  useAutoPlanRunStore,
} from '../stores/autoPlanRunStore'
import AutoPlanConfirmForm from './AutoPlanConfirmForm.vue'
import AutoPlanRunningView from './AutoPlanRunningView.vue'
import AutoPlanObserverView from './AutoPlanObserverView.vue'
import AutoPlanResultsView from './AutoPlanResultsView.vue'

import type { MachinePoolResponse, ProductionMachineResponse } from '@/features/production-machines'
import type {
  AutoPlanAlgorithm,
  AutoPlanOrderDiffResponse,
  AutoPlanPlanningLevel,
  AutoPlanResponse,
  AutoPlanSkippedOrderResponse,
} from '../types/scheduleBoardResponse'

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  applied: []
}>()

const { t } = useI18n()
const adminSettingsStore = useAdminSettingsStore()
const runStore = useAutoPlanRunStore()

type Step = 'confirm' | 'running' | 'observing' | 'results'

const step = ref<Step>('confirm')
const machines = ref<ProductionMachineResponse[]>([])
const machinesLoaded = ref(false)
const loadingMachines = ref(false)
watchLoadingBar(loadingMachines)
// Pools only label pool moves in the progress feed and results. They are
// fetched here because the queue store may not be initialised wherever this
// dialog is mounted.
const pools = ref<MachinePoolResponse[]>([])
const poolsLoaded = ref(false)
const loadingPools = ref(false)
watchLoadingBar(loadingPools)

// Option defaults match the backend's, except the planning level: pools
// keeps a pool-assigned order at its pool for later resolution.
const selectedMachines = ref<ProductionMachineResponse[]>([])
const assignMachines = ref(false)
const planningLevel = ref<AutoPlanPlanningLevel>('pools')
const overwritePinned = ref(false)
const excludeTodaysPlanned = ref(true)
// Pre-filled from the admin production setting on every fresh open and sent
// as a per-run override without changing that standing default.
const responseTimeDays = ref(1)
const algorithm = ref<AutoPlanAlgorithm>('urgent_first')

// Opens the handbook page with the picked algorithm highlighted.
const explainVisible = ref(false)

const running = ref(false)
const errorMessage = ref<string | null>(null)
const warnMessage = ref<string | null>(null)
// Names who finished a run this dialog was only observing; not a problem.
const infoMessage = ref<string | null>(null)
const results = reactive<{
  proposals: AutoPlanOrderDiffResponse[]
  skipped: number
  skippedTodaysPlanned: number
  // Orders the planner could not place, as opposed to the two counters of
  // orders deliberately left alone.
  skippedOrders: AutoPlanSkippedOrderResponse[]
}>({
  proposals: [],
  skipped: 0,
  skippedTodaysPlanned: 0,
  skippedOrders: [],
})

// True while this dialog's own onConfirm() runs, so the attach watcher does
// not handle the outcome of a run this instance started.
const ownRunActive = ref(false)

const machineNameById = computed<Record<number, string>>(() =>
  Object.fromEntries(machines.value.map((m) => [m.id, m.internal_name])),
)

const poolNameById = computed<Record<number, string>>(() =>
  Object.fromEntries(pools.value.map((p) => [p.id, p.name])),
)

// The static defaults are set right on open; the machine selection and the
// response time need the machines and settings loaded first.
function resetConfirmDefaults(): void {
  assignMachines.value = false
  planningLevel.value = 'pools'
  overwritePinned.value = false
  excludeTodaysPlanned.value = true
  algorithm.value = 'urgent_first'
}

function applyConfirmFormDefaults(): void {
  responseTimeDays.value = adminSettingsStore.settings?.production.response_time_days ?? 1
  selectedMachines.value = [...machines.value]
}

function showResults(response: AutoPlanResponse): void {
  results.proposals = response.proposals ?? []
  results.skipped = response.skipped_pinned_or_in_progress
  results.skippedTodaysPlanned = response.skipped_todays_planned
  results.skippedOrders = response.skipped ?? []
  step.value = 'results'
  emit('applied')
}

watch(visible, async (isVisible) => {
  if (!isVisible) {
    runStore.stopObserverPolling()
    return
  }
  errorMessage.value = null
  warnMessage.value = null
  infoMessage.value = null

  // A run of this user already in flight (started from another mounted
  // instance) attaches to the running view; someone else's run opens the
  // observer view. Otherwise the confirm form starts fresh.
  const attaching = runStore.status === 'running'
  const observingOther = !attaching && runStore.anyRunActive && !runStore.isMine
  if (attaching) {
    step.value = 'running'
  } else if (observingOther) {
    step.value = 'observing'
    // Reopening on the same run leaves `step` unchanged, so the step watcher
    // would not start the poll.
    runStore.startObserverPolling()
  } else {
    step.value = 'confirm'
    resetConfirmDefaults()
  }

  // Every step needs the machine and pool names, not only the confirm form.
  if (!machinesLoaded.value) {
    loadingMachines.value = true
    try {
      const result = await getProductionMachines({ limit: API_MAX_PAGE_SIZE, include_archived: true })
      machines.value = result.items
      machinesLoaded.value = true
    } finally {
      loadingMachines.value = false
    }
  }
  if (!poolsLoaded.value) {
    loadingPools.value = true
    try {
      const result = await getMachinePools({ limit: API_MAX_PAGE_SIZE, include_archived: true })
      pools.value = result.items
      poolsLoaded.value = true
    } finally {
      loadingPools.value = false
    }
  }
  if (!adminSettingsStore.settings) await adminSettingsStore.fetch()

  if (!attaching && !observingOther) {
    applyConfirmFormDefaults()
  }
})

// The observer poll runs exactly while the step is 'observing'. Closing and
// unmounting do not change the step, so they stop it separately.
watch(step, (newStep, oldStep) => {
  if (newStep === 'observing') {
    runStore.startObserverPolling()
  } else if (oldStep === 'observing') {
    runStore.stopObserverPolling()
  }
})

// When an observed run ends, the form returns and names who finished it.
// activeRun is already null by then, hence the previous value.
watch(
  () => runStore.activeRun,
  (activeRun, previousActiveRun) => {
    if (!visible.value || step.value !== 'observing' || activeRun !== null) return
    step.value = 'confirm'
    resetConfirmDefaults()
    applyConfirmFormDefaults()
    infoMessage.value = previousActiveRun
      ? t('productionSchedule.autoPlan.observer.finished', { user: previousActiveRun.user_name })
      : null
  },
)

onBeforeUnmount(() => {
  runStore.stopObserverPolling()
})

// A dialog that attached to a running run picks up its outcome from the
// store. The run this instance started is handled in onConfirm instead.
watch(
  () => [runStore.result, runStore.errorDetail, runStore.connectionLost] as const,
  ([result, errorDetail, connectionLost]) => {
    if (ownRunActive.value || !visible.value || step.value !== 'running') return
    if (result) {
      showResults(result)
    } else if (connectionLost) {
      step.value = 'confirm'
      warnMessage.value = t('productionSchedule.autoPlan.errors.connectionLost')
    } else if (errorDetail) {
      step.value = 'confirm'
      errorMessage.value = errorDetail
    }
  },
)

async function onConfirm(): Promise<void> {
  running.value = true
  errorMessage.value = null
  warnMessage.value = null
  step.value = 'running'
  ownRunActive.value = true
  try {
    const response = await runStore.run({
      machine_ids: selectedMachines.value.map((m) => m.id),
      assign_machines: assignMachines.value,
      planning_level: planningLevel.value,
      overwrite_pinned: overwritePinned.value,
      exclude_todays_planned: excludeTodaysPlanned.value,
      algorithm: algorithm.value,
      response_time_days: responseTimeDays.value,
    })
    showResults(response)
  } catch (e) {
    if (e instanceof AutoPlanAlreadyRunningError) {
      // A stale confirm view; the run is live, so attach to it.
      step.value = 'running'
    } else if (e instanceof AutoPlanRunTakenError) {
      // Lost the race to another run, which is not an error to the user.
      // The store already holds the winner and the step watcher polls it.
      step.value = 'observing'
    } else if (e instanceof AutoPlanConnectionLostError) {
      step.value = 'confirm'
      warnMessage.value = t('productionSchedule.autoPlan.errors.connectionLost')
    } else if (e instanceof SseHttpError) {
      step.value = 'confirm'
      errorMessage.value = t('productionSchedule.autoPlan.errors.unknown')
    } else if (e instanceof Error && e.message) {
      // The backend's detail message, forwarded by the stream API.
      step.value = 'confirm'
      errorMessage.value = e.message
    } else {
      step.value = 'confirm'
      errorMessage.value = t('productionSchedule.autoPlan.errors.unknown')
    }
  } finally {
    running.value = false
    ownRunActive.value = false
  }
}

function onClose(): void {
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-lg)' }"
    :pt="{
      header: { 'data-testid': 'autoplan-dialog-header' },
      footer: { 'data-testid': 'autoplan-dialog-footer' },
    }"
  >
    <!-- Own header row so the explain button can sit right of the title and
         left of the Dialog's own close icon. -->
    <template #header>
      <div class="autoplan-header">
        <span class="p-dialog-title">{{ t('productionSchedule.autoPlan.title') }}</span>
        <!-- Same shape as the Dialog's own close button it sits next to. -->
        <Button
          type="button"
          class="autoplan-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('productionSchedule.autoPlan.explain.trigger')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('productionSchedule.autoPlan.explain.tooltip')"
          @click="explainVisible = true"
        />
      </div>
    </template>

    <AutoPlanConfirmForm
      v-if="step === 'confirm'"
      v-model:planning-level="planningLevel"
      v-model:algorithm="algorithm"
      v-model:response-time-days="responseTimeDays"
      v-model:selected-machines="selectedMachines"
      v-model:assign-machines="assignMachines"
      v-model:overwrite-pinned="overwritePinned"
      v-model:exclude-todays-planned="excludeTodaysPlanned"
      :machines="machines"
      :error-message="errorMessage"
      :warn-message="warnMessage"
      :info-message="infoMessage"
    />

    <AutoPlanRunningView
      v-else-if="step === 'running'"
      :machine-name-by-id="machineNameById"
      :pool-name-by-id="poolNameById"
    />

    <AutoPlanObserverView v-else-if="step === 'observing'" />

    <AutoPlanResultsView
      v-else-if="step === 'results'"
      :results="results"
      :machine-name-by-id="machineNameById"
      :pool-name-by-id="poolNameById"
    />

    <template #footer>
      <Button
        v-if="step === 'confirm'"
        :label="t('common.cancel')"
        severity="secondary"
        :disabled="running"
        @click="onClose"
      />
      <Button
        v-if="step === 'confirm'"
        :label="t('productionSchedule.autoPlan.run')"
        :loading="running"
        :disabled="
          selectedMachines.length === 0 ||
          runStore.status === 'running' ||
          (runStore.anyRunActive && !runStore.isMine)
        "
        @click="onConfirm"
      />
      <Button
        v-if="step === 'results'"
        :label="t('common.close')"
        severity="secondary"
        @click="onClose"
      />
    </template>
  </Dialog>

  <HelpDrawer
    v-model:visible="explainVisible"
    slug="production/auto-plan"
    :context="{ algorithm }"
  />
</template>

<style scoped lang="scss">
// Fills the header row so the explain button lands right before the
// Dialog's own close icon.
.autoplan-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

// Matches the close button's 14px icon instead of the icon font's default.
.autoplan-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}
</style>
