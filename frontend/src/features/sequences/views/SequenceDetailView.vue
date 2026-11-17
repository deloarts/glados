<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useConfirm } from 'openvue/useconfirm'
import { useMediaQuery } from '@vueuse/core'

import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePageTitle } from '@/core/composables/usePageTitle'
import { usePermissions } from '@/core/composables/usePermissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { extractApiError } from '@/core/utils/errors'
import { ProductDeviceDialog } from '@/features/product-devices'
import type { ProductDevice } from '@/features/product-devices'
import { ProductDeviceCalculations } from '@/features/tools'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import { useConfirmAsync } from '@/shared/composables/useConfirmAsync'
import { useLeaveGuard } from '@/shared/composables/useLeaveGuard'
import { useResizablePanelWidth } from '@/shared/composables/useResizablePanelWidth'
import {
  DocumentDraftDialog,
  DocumentInvalidNotice,
  DocumentLockNotice,
  DocumentReasonDialog,
  useDocumentPageAction,
} from '@/shared/documents'
import type { DocumentPageAction } from '@/shared/documents'
import SequenceControls from '../components/SequenceControls.vue'
import SequenceDisplacementDiagram from '../components/SequenceDisplacementDiagram.vue'
import SequenceEditor from '../components/SequenceEditor.vue'
import SequenceGrafcet from '../components/SequenceGrafcet.vue'
import SequenceHistoryDialog from '../components/SequenceHistoryDialog.vue'
import SequenceInfo from '../components/SequenceInfo.vue'
import SequenceStartState from '../components/SequenceStartState.vue'
import SequenceViews from '../components/SequenceViews.vue'
import { useSequenceDocument } from '../composables/useSequenceDocument'
import { useSequenceTiming } from '../composables/useSequenceTiming'
import { sequenceLocation } from '../utils/routes'
import { isSequenceView } from '../utils/views'
import type { SequenceView } from '../utils/views'
import PanelResizeHandle from '@/shared/components/layout/PanelResizeHandle.vue'

/**
 * /workspace/products/:id/sequences/:sequenceId/:view?, one revision of a
 * flow sequence with its views: the editor, the start state, the
 * displacement-step diagram and the GRAFCET chart. On a wide screen the
 * editor has the GRAFCET chart beside it, following the steps as they
 * change. The latest, unreleased
 * revision is edited here after Edit takes its lock; a released or older
 * one, or one somebody else is editing, is shown read-only.
 */

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useAppToast()
const confirm = useConfirm()
const hostStore = useHostStore()
const { ask } = useConfirmAsync()

const sequenceId = computed(() => Number(route.params.sequenceId))
const doc = useSequenceDocument(sequenceId)
const timing = useSequenceTiming(doc)
watchLoadingBar(doc.loading)

const sequence = computed(() => doc.sequence.value)
const title = computed(() => sequence.value?.name ?? t('sequences.title'))

const view = computed<SequenceView>({
  get: () => (isSequenceView(route.params.view) ? route.params.view : 'editor'),
  // A named location, since a relative one keeps the current view when the
  // editor, which has none in the address, is picked.
  set: (next) => {
    const current = sequence.value
    if (!current) return
    void router.replace(sequenceLocation(current, { view: next === 'editor' ? undefined : next }))
  },
})

// The GRAFCET panel on the right of the editor, from 1400px up; dragging
// its leading edge resizes it, and the width is remembered.
const wide = useMediaQuery('(min-width: 1400px)')
const grafcetPanel = computed(() => wide.value && view.value === 'editor' && !!sequence.value)
const {
  width: grafcetWidth,
  isResizing: isResizingGrafcet,
  onResizeStart: onGrafcetResizeStart,
  onResizeKey: onGrafcetResizeKey,
  min: grafcetMin,
  max: grafcetMax,
} = useResizablePanelWidth({
  defaultWidth: 560,
  min: 320,
  max: () => window.innerWidth * 0.6,
  dockedTo: 'end',
  storageKey: 'glados.sequences.grafcetPanelWidth',
})

// A device opened from the start state, edited as on the product's devices
// tab: by a manager, or by its designated user, while the product is live.
const { hasPermission } = usePermissions()
const currentUserStore = useCurrentUserStore()
const canEditDevices = computed(() => {
  const product = doc.product.value
  if (!product || product.archived) return false
  if (hasPermission(Permission.MANAGE_PROJECTS)) return true
  return hasPermission(Permission.WRITE_PROJECTS) && product.designated_user_id === currentUserStore.user?.id
})
const deviceVisible = ref(false)
const openedDevice = ref<ProductDevice | undefined>(undefined)

function openDevice(deviceId: number): void {
  openedDevice.value = doc.devices.value.find((device) => device.id === deviceId)
  if (openedDevice.value) deviceVisible.value = true
}

function onDeviceSaved(saved: ProductDevice): void {
  doc.replaceDevice(saved)
  toast.success(saved.name_utf8, t('productDevices.devices.saved'))
}

/** The newest revision, linked from an older one. */
const latest = computed(() => doc.revisions.value[0] ?? null)

const reviseVisible = ref(false)
const historyVisible = ref(false)
const invalidVisible = ref(false)

function fail(e: unknown): void {
  toast.error(title.value, extractApiError(e) ?? t('sequences.errors.unknown'))
}

async function onMarkInvalid(reason: string): Promise<void> {
  try {
    await doc.markInvalid(reason)
    invalidVisible.value = false
    toast.success(title.value, t('documents.invalid.done'))
  } catch (e) {
    fail(e)
  }
}

async function onRevise(reason: string): Promise<void> {
  try {
    const created = await doc.revise(reason)
    reviseVisible.value = false
    if (!created) return
    toast.success(created.name, t('sequences.toasts.revised', { revision: created.revision }))
    await router.push(sequenceLocation(created))
  } catch (e) {
    fail(e)
  }
}

// Taking over drops the other editor's unsaved changes, so it asks first.
function takeOver(): void {
  const by = doc.lock.lockedByOther.value?.name ?? ''
  confirm.require({
    group: 'sequence-leave',
    header: t('documents.lock.takeOver'),
    message: t('documents.lock.takeOverConfirm', { name: by }),
    icon: 'mdi mdi-alert-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('documents.lock.takeOver'), severity: 'warn' },
    accept: () => void doc.startEditing(true).catch(fail),
  })
}

function endEditing(): void {
  const by = doc.lock.lockedByOther.value?.name ?? ''
  confirm.require({
    group: 'sequence-leave',
    header: t('documents.lock.end'),
    message: t('documents.lock.endConfirm', { name: by }),
    icon: 'mdi mdi-alert-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('documents.lock.end'), severity: 'warn' },
    accept: () => void doc.lock.endOthersEditing().catch(fail),
  })
}

watch(
  () => doc.lostBy.value.length,
  () => {
    const by = doc.lostBy.value.at(-1)
    toast.warn(title.value, by ? t('documents.lock.lost', { name: by }) : t('documents.lock.lostUnknown'))
  },
)
watch(
  () => doc.idleEnded.value,
  () => toast.warn(title.value, t('documents.lock.idle')),
)

function openRevision(id: number): void {
  historyVisible.value = false
  const current = sequence.value
  if (current) void router.push(sequenceLocation({ id, product_id: current.product_id }))
}

// Leaving with unsaved steps asks first, also for another revision of the
// same sequence; switching between the page's views keeps them.
const leaveGuard = useLeaveGuard({
  dirty: () => doc.dirty.value,
  updates: (to, from) => to.params.sequenceId !== from.params.sequenceId,
  confirm: () =>
    ask({
      group: 'sequence-leave',
      header: t('documents.leave.header'),
      message: t('documents.leave.message'),
      icon: 'mdi mdi-alert-outline',
      rejectProps: { label: t('common.cancel'), severity: 'secondary' },
      acceptProps: { label: t('documents.leave.accept'), severity: 'warn' },
    }),
})

// After deleting a revision the one before it is the latest again; without
// one the page goes back to the product's sequences.
async function onDeleted(): Promise<void> {
  const current = sequence.value
  const before = doc.revisions.value.find((r) => r.id !== current?.id)
  leaveGuard.allowNext()
  if (current && before) {
    await router.replace(sequenceLocation(before))
    return
  }
  await router.replace({ name: 'ProductDetail', params: { id: route.params.id, tab: 'sequences' } })
}

const controls = ref<InstanceType<typeof SequenceControls> | null>(null)

// A list's row menu leaves these steps to the page, which starts them like
// its own buttons do once the sequence is loaded.
useDocumentPageAction({
  ready: () => !!sequence.value && !doc.loading.value && controls.value !== null,
  run: (action: DocumentPageAction): boolean => {
    switch (action) {
      case 'edit':
        return controls.value?.edit() ?? false
      case 'release':
        return controls.value?.release() ?? false
      case 'history':
        historyVisible.value = true
        return true
      case 'invalidate':
        if (doc.canMarkInvalid.value) invalidVisible.value = true
        return doc.canMarkInvalid.value
      case 'revise':
        if (doc.canRevise.value) reviseVisible.value = true
        return doc.canRevise.value
      case 'copy':
        return false
    }
  },
})

async function onRestoreDraft(): Promise<void> {
  try {
    await doc.restoreDraft()
    toast.success(title.value, t('documents.draft.restored'))
  } catch (e) {
    fail(e)
  }
}

const { setPageTitle } = usePageTitle()
watch(title, (value) => setPageTitle(value), { immediate: true })
</script>

<template>
  <PageLayout :card="false" :class="{ 'is-resizing-ew': isResizingGrafcet }" data-class="sequence-view-data">
    <template #info>
      <SequenceInfo :doc="doc" :timing="timing" />
    </template>
    <template v-if="sequence" #controls>
      <SequenceControls
        ref="controls"
        :doc="doc"
        @history="historyVisible = true"
        @revise="reviseVisible = true"
        @invalidate="invalidVisible = true"
        @deleted="onDeleted"
      />
    </template>
    <template v-if="sequence" #views>
      <SequenceViews v-model:view="view" :timing="timing" />
    </template>

    <template v-if="grafcetPanel" #panels-end>
      <PanelResizeHandle data-testid="sequence-grafcet-resize" :width="grafcetWidth" :min="grafcetMin" :max="grafcetMax" @start="onGrafcetResizeStart" @key="onGrafcetResizeKey" />
      <section class="card grafcet-panel" :style="{ width: `${grafcetWidth}px` }" data-testid="sequence-grafcet-panel">
        <span class="section-label">{{ t('sequences.views.grafcet') }}</span>
        <SequenceGrafcet :doc="doc" :timing="timing" :framed="false" class="grafcet-panel-chart" />
      </section>
    </template>

    <div v-if="doc.loadFailed.value" class="state-message">
      <i class="mdi mdi-alert-circle-outline state-icon" aria-hidden="true" />
      <span>{{ t('sequences.errors.notFound') }}</span>
    </div>

    <div v-else-if="sequence" class="detail">
      <DocumentInvalidNotice :document="sequence" />
      <DocumentLockNotice
        v-if="doc.lock.lockedByOther.value"
        :name="doc.lock.lockedByOther.value.name"
        :since="doc.lock.lockedByOther.value.since"
        :can-take-over="doc.canTakeOver.value"
        :take-over-blocked="doc.takeOverBlocked.value"
        :busy="doc.lock.busy.value"
        @take-over="takeOver"
        @end="endEditing"
      />
      <Message v-if="!sequence.is_latest && latest" severity="info" data-testid="sequence-not-latest">
        {{ t('sequences.notices.notLatest', { revision: latest.revision }) }}
        <RouterLink :to="sequenceLocation(latest)">{{ t('sequences.notices.openLatest') }}</RouterLink>
      </Message>

      <SequenceEditor
        v-if="view === 'editor'"
        v-model:name="doc.name.value"
        v-model:steps="doc.steps.value"
        :doc="doc"
        :timing="timing"
        class="view"
      />
      <SequenceStartState
        v-else-if="view === 'initial'"
        :doc="doc"
        :names="timing.names"
        class="view"
        @open="openDevice"
      />
      <SequenceDisplacementDiagram v-else-if="view === 'diagram'" :doc="doc" :timing="timing" class="view" />
      <SequenceGrafcet v-else :doc="doc" :timing="timing" class="view" />
    </div>

    <DocumentReasonDialog
      v-if="sequence"
      v-model:visible="reviseVisible"
      :header="t('sequences.revise.title')"
      :intro="t('sequences.revise.intro', { revision: sequence.revision })"
      :submit-label="t('sequences.revise.submit')"
      submit-icon="mdi mdi-file-replace-outline"
      :busy="doc.busy.value"
      @submit="onRevise"
    />
    <DocumentReasonDialog
      v-if="sequence"
      v-model:visible="invalidVisible"
      :header="t('documents.invalid.title', { revision: sequence.revision })"
      :intro="t('documents.invalid.intro')"
      :submit-label="t('documents.invalid.submit')"
      submit-icon="mdi mdi-cancel"
      severity="danger"
      :busy="doc.busy.value"
      @submit="onMarkInvalid"
    />
    <SequenceHistoryDialog
      v-if="sequence"
      v-model:visible="historyVisible"
      :revisions="doc.revisions.value"
      :current-id="sequence.id"
      @open="openRevision"
    />
    <ProductDeviceDialog
      v-if="sequence"
      v-model:visible="deviceVisible"
      :product-id="sequence.product_id"
      :device="openedDevice"
      :devices="doc.devices.value"
      :disciplines="
        doc.product.value
          ? {
              pneumatics: doc.product.value.contains_pneumatics,
              hydraulics: doc.product.value.contains_hydraulics,
              electrics: doc.product.value.contains_electrics,
              robotics: doc.product.value.contains_robotics,
            }
          : undefined
      "
      :readonly="!canEditDevices"
      @saved="onDeviceSaved"
    >
      <template v-if="hostStore.calculationsEnabled" #calculations="{ device, onLoaded }">
        <ProductDeviceCalculations :device="device" @loaded="onLoaded" />
      </template>
    </ProductDeviceDialog>
    <ConfirmDialog group="sequence-leave" />
    <DocumentDraftDialog
      :offer="doc.draft.offer.value"
      :blocked="doc.draftBlocked.value"
      :saved-since="sequence?.changed ?? null"
      :busy="doc.lock.busy.value"
      @restore="onRestoreDraft"
      @discard="doc.draft.discard()"
      @dismiss="doc.draft.dismiss()"
    />
  </PageLayout>
</template>

<style scoped lang="scss">
.detail {
  flex: 1 1 auto;
  min-width: 0;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);

  > :not(.view) {
    flex-shrink: 0;
  }

  > .view {
    flex: 1 1 auto;
    min-height: 0;
  }
}

// The views scroll inside themselves, never the page; with the GRAFCET
// panel the data area is a row, the drag handle giving the spacing.
:deep(.sequence-view-data) {
  overflow: hidden;
  display: flex;
  gap: var(--space-1);
}

.grafcet-panel {
  flex: 0 0 auto;
  min-width: 0;
  gap: var(--space-1);

  .section-label {
    flex-shrink: 0;
  }

  .grafcet-panel-chart {
    flex: 1 1 auto;
  }
}

.is-resizing-ew {
  user-select: none;
  cursor: ew-resize;
}

.state-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: var(--space-3);
  padding: var(--space-6);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-md);

  .state-icon {
    font-size: var(--font-size-3xl);
  }
}
</style>
