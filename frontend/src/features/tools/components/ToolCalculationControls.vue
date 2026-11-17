<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ShareButton from '@/shared/components/resource-view/ShareButton.vue'
import { HelpButton } from '@/shared/help'
import { DocumentInvalidNotice, DocumentLockNotice, DocumentReasonDialog, useDocumentPageAction } from '@/shared/documents'
import type { DocumentAction, DocumentPageAction } from '@/shared/documents'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import { ownerOf, toolPath } from '../composables/useSavedCalculation'
import type { CalculationMeta, SavedCalculation } from '../composables/useSavedCalculation'
import type { CalculationOwner, CalculationSummaryResponse } from '../types/calculation'
import CalculationDriftNotice from './CalculationDriftNotice.vue'
import CalculationHistoryDialog from './CalculationHistoryDialog.vue'
import LoadCalculationDialog from './LoadCalculationDialog.vue'
import SaveCalculationDialog from './SaveCalculationDialog.vue'

/**
 * The actions of a saveable tool, laid out like a checklist's. For an open
 * calculation: Release, Edit, New Revision, Mark as Invalid and Delete, as
 * far as the calculation's state allows them, and one the user lacks the
 * rights for shown disabled with the missing permission; while editing
 * Save, Release (which saves the changes first and ends editing), Done,
 * which reads Discard while there are unsaved changes, Delete and Edit
 * details.
 * Without one: Save. Then History and Print, and after another divider the
 * tool's own New, Load and Save as New, which leave the
 * editing out. Anything that would throw away unsaved edits asks first.
 */

const props = defineProps<{
  saved: SavedCalculation
  toolKey: string
  tab: string
  /** Title proposed for a new calculation, from the tool. */
  defaultTitle: string
  /** Owner proposed for a new calculation, e.g. when the tool was opened from a project. */
  defaultOwner: CalculationOwner
  /** Device proposed for a new calculation, when the tool was opened from one. */
  defaultDeviceId?: number | null
}>()

const emit = defineEmits<{ print: [] }>()

const { t } = useI18n()
const toast = useAppToast()
const confirm = useConfirm()

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const loadVisible = ref(false)
const reviseVisible = ref(false)
const historyVisible = ref(false)

function openRevision(publicId: string): void {
  historyVisible.value = false
  guardedLoad(() => void props.saved.open(publicId))
}
const invalidVisible = ref(false)

const calc = computed(() => props.saved.calculation.value)

const dialogInitial = computed<CalculationMeta>(() => {
  const c = calc.value
  if (dialogMode.value === 'edit' && c) {
    return { owner: ownerOf(c), title: c.title, note: c.note, deviceId: c.product_device_id }
  }
  return {
    owner: c ? ownerOf(c) : props.defaultOwner,
    title: props.defaultTitle,
    note: null,
    deviceId: c ? c.product_device_id : (props.defaultDeviceId ?? null),
  }
})

function openDialog(mode: 'create' | 'edit'): void {
  dialogMode.value = mode
  dialogVisible.value = true
}

async function attempt(action: () => Promise<unknown>, success: string): Promise<boolean> {
  try {
    await action()
    toast.success(t('tools.calculations.title'), success)
    return true
  } catch (e) {
    toast.error(t('tools.calculations.title'), extractApiError(e) ?? t('tools.calculations.errors.unknown'))
    return false
  }
}

async function onDialogSave(meta: CalculationMeta): Promise<void> {
  const ok =
    dialogMode.value === 'create'
      ? await attempt(() => props.saved.saveNew(meta), t('tools.calculations.toasts.saved'))
      : await attempt(() => props.saved.save(meta), t('tools.calculations.toasts.saved'))
  if (ok) dialogVisible.value = false
}

// Save writes into the open calculation while the user edits it; without
// one open it saves a new calculation, and next to an open one Save as New
// keeps what is on screen as an independent calculation.
const savesInPlace = computed(() => !!calc.value && props.saved.canUpdate.value)
const canSave = computed(() => savesInPlace.value || props.saved.canCreate.value)
const saveDisabled = computed(
  () => savesInPlace.value && !props.saved.dirty.value && !props.saved.drift.value,
)

function onSave(): void {
  if (savesInPlace.value) void attempt(() => props.saved.save(), t('tools.calculations.toasts.saved'))
  else openDialog('create')
}

/** Why an offered button cannot be pressed: the permission the user lacks. */
function blockedBy(action: DocumentAction): string {
  const permission = props.saved.missing.value[action]
  return permission ? t('documents.permissionMissing', { permission: permissionLabel(t, permission) }) : ''
}

async function onRevise(reason: string): Promise<void> {
  try {
    const created = await props.saved.revise(reason)
    reviseVisible.value = false
    if (created) {
      toast.success(t('tools.calculations.title'), t('tools.calculations.toasts.revised', { revision: created.revision }))
    }
  } catch (e) {
    toast.error(t('tools.calculations.title'), extractApiError(e) ?? t('tools.calculations.errors.unknown'))
  }
}

async function onMarkInvalid(reason: string): Promise<void> {
  if (await attempt(() => props.saved.markInvalid(reason), t('documents.invalid.done'))) invalidVisible.value = false
}

// Taking over drops the other editor's unsaved changes, so it asks first.
function takeOver(): void {
  confirm.require({
    group: 'tool-calculation',
    header: t('documents.lock.takeOver'),
    message: t('documents.lock.takeOverConfirm', { name: props.saved.lock.lockedByOther.value?.name ?? '' }),
    icon: 'mdi mdi-alert-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('documents.lock.takeOver'), severity: 'warn' },
    accept: () => {
      props.saved.startEditing(true).catch((e: unknown) => {
        toast.error(t('tools.calculations.title'), extractApiError(e) ?? t('tools.calculations.errors.unknown'))
      })
    },
  })
}

function endEditing(): void {
  confirm.require({
    group: 'tool-calculation',
    header: t('documents.lock.end'),
    message: t('documents.lock.endConfirm', { name: props.saved.lock.lockedByOther.value?.name ?? '' }),
    icon: 'mdi mdi-alert-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('documents.lock.end'), severity: 'warn' },
    accept: () => {
      props.saved.lock.endOthersEditing().catch((e: unknown) => {
        toast.error(t('tools.calculations.title'), extractApiError(e) ?? t('tools.calculations.errors.unknown'))
      })
    },
  })
}

watch(
  () => props.saved.lostBy.value.length,
  () => {
    const by = props.saved.lostBy.value.at(-1)
    toast.warn(t('tools.calculations.title'), by ? t('documents.lock.lost', { name: by }) : t('documents.lock.lostUnknown'))
  },
)

watch(
  () => props.saved.idleEnded.value,
  () => toast.warn(t('tools.calculations.title'), t('documents.lock.idle')),
)

function edit(): void {
  props.saved.startEditing().catch((e: unknown) => {
    toast.error(t('tools.calculations.title'), extractApiError(e) ?? t('tools.calculations.errors.unknown'))
  })
}

function discard(): void {
  if (!props.saved.dirty.value) {
    void props.saved.finishEditing()
    return
  }
  confirm.require({
    group: 'tool-calculation',
    header: t('documents.lock.discard'),
    message: t('documents.lock.discardConfirm'),
    icon: 'mdi mdi-alert-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('documents.lock.discard'), severity: 'danger' },
    accept: () => void props.saved.finishEditing(),
  })
}

type ConfirmKey = 'new' | 'load' | 'release' | 'delete'

function ask(key: ConfirmKey, action: () => unknown): void {
  const warning = key === 'new' || key === 'load'
  confirm.require({
    group: 'tool-calculation',
    header: t(`tools.calculations.confirm.${key}.header`),
    // The message ends in a question, so a note on saving goes first.
    message: [
      key === 'release' && props.saved.editing.value && props.saved.releaseSavesFirst.value
        ? t('tools.calculations.confirm.release.saveFirst')
        : '',
      t(`tools.calculations.confirm.${key}.message`),
    ]
      .filter(Boolean)
      .join(' '),
    icon: key === 'delete' || warning ? 'mdi mdi-alert-outline' : 'mdi mdi-check-decagram-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: {
      label: t(`tools.calculations.confirm.${key}.accept`),
      severity: key === 'delete' ? 'danger' : warning ? 'warn' : 'primary',
    },
    accept: action,
  })
}

/** Opens the load dialog, asking first if that would lose edits. */
function guardedLoad(action: () => unknown): void {
  if (props.saved.hasUnsavedChanges.value) ask('load', action)
  else action()
}

function onNew(): void {
  ask('new', () => props.saved.startNew())
}

function onLoad(): void {
  guardedLoad(() => (loadVisible.value = true))
}

// A list's row menu leaves these steps to the page, which starts them like
// its own buttons do once the calculation and the tool are ready.
useDocumentPageAction({
  ready: () => !!props.saved.calculation.value && !props.saved.resolving.value && props.saved.toolReady.value,
  run: (action: DocumentPageAction): boolean => {
    const s = props.saved
    switch (action) {
      case 'edit':
        if (s.canEdit.value) edit()
        return s.canEdit.value
      case 'history':
        historyVisible.value = true
        return true
      case 'release':
        if (s.canRelease.value) ask('release', () => attempt(s.release, t('tools.calculations.toasts.release')))
        return s.canRelease.value
      case 'invalidate':
        if (s.canMarkInvalid.value) invalidVisible.value = true
        return s.canMarkInvalid.value
      case 'revise':
        if (s.canRevise.value) reviseVisible.value = true
        return s.canRevise.value
      case 'copy':
        if (s.canCreate.value) openDialog('create')
        return s.canCreate.value
    }
  },
})

function onLoaded(row: CalculationSummaryResponse): void {
  void props.saved.open(row.public_id)
}
</script>

<template>
  <ControlsBar data-testid="tool-calculation-controls">
    <template #start>
      <!-- Editing the open draft. -->
      <template v-if="saved.editing.value">
        <Button
          :label="t('tools.calculations.actions.save')"
          icon="mdi mdi-content-save-outline"
          severity="contrast"
          text
          :disabled="saveDisabled"
          :loading="saved.busy.value"
          data-testid="calc-save"
          @click="onSave"
        />
        <span v-if="saved.offered.value.release" v-tooltip.bottom="blockedBy('release')">
          <Button
            :label="t('tools.calculations.actions.release')"
            icon="mdi mdi-check-decagram-outline"
            severity="contrast"
            text
            :disabled="!saved.canRelease.value || saved.busy.value"
            data-testid="calc-release"
            @click="ask('release', () => attempt(saved.release, t('tools.calculations.toasts.release')))"
          />
        </span>
        <Button
          :label="saved.dirty.value ? t('documents.lock.discard') : t('tools.calculations.actions.done')"
          :icon="saved.dirty.value ? 'mdi mdi-close-circle-outline' : 'mdi mdi-check'"
          severity="contrast"
          text
          :loading="saved.lock.busy.value"
          data-testid="calc-finish"
          @click="discard"
        />
        <span v-if="saved.offered.value.delete" v-tooltip.bottom="blockedBy('delete')">
          <Button
            :label="t('common.delete')"
            icon="mdi mdi-delete-outline"
            severity="contrast"
            text
            :disabled="!saved.canDelete.value"
            data-testid="calc-delete"
            @click="ask('delete', () => attempt(saved.remove, t('tools.calculations.toasts.delete')))"
          />
        </span>
        <Button
          :label="t('tools.calculations.actions.editDetails')"
          icon="mdi mdi-form-textbox"
          severity="contrast"
          text
          data-testid="calc-edit-details"
          @click="openDialog('edit')"
        />
      </template>

      <!-- A saved calculation, not being edited by this user. -->
      <template v-else-if="calc">
        <span v-if="saved.offered.value.release" v-tooltip.bottom="blockedBy('release')">
          <Button
            :label="t('tools.calculations.actions.release')"
            icon="mdi mdi-check-decagram-outline"
            severity="contrast"
            text
            :disabled="!saved.canRelease.value"
            data-testid="calc-release"
            @click="ask('release', () => attempt(saved.release, t('tools.calculations.toasts.release')))"
          />
        </span>
        <span v-if="saved.offered.value.edit" v-tooltip.bottom="blockedBy('edit')">
          <Button
            :label="t('documents.lock.edit')"
            icon="mdi mdi-pencil-outline"
            severity="contrast"
            text
            :disabled="!saved.canEdit.value"
            :loading="saved.lock.busy.value"
            data-testid="calc-edit"
            @click="edit"
          />
        </span>
        <span v-if="saved.offered.value.revise" v-tooltip.bottom="blockedBy('revise')">
          <Button
            :label="t('tools.calculations.actions.revise')"
            icon="mdi mdi-file-replace-outline"
            severity="contrast"
            text
            :disabled="!saved.canRevise.value"
            data-testid="calc-revise"
            @click="reviseVisible = true"
          />
        </span>
        <span v-if="saved.offered.value.invalidate" v-tooltip.bottom="blockedBy('invalidate')">
          <Button
            :label="t('documents.invalid.action')"
            icon="mdi mdi-cancel"
            severity="contrast"
            text
            :disabled="!saved.canMarkInvalid.value"
            data-testid="calc-mark-invalid"
            @click="invalidVisible = true"
          />
        </span>
        <span v-if="saved.offered.value.delete" v-tooltip.bottom="blockedBy('delete')">
          <Button
            :label="t('common.delete')"
            icon="mdi mdi-delete-outline"
            severity="contrast"
            text
            :disabled="!saved.canDelete.value"
            data-testid="calc-delete"
            @click="ask('delete', () => attempt(saved.remove, t('tools.calculations.toasts.delete')))"
          />
        </span>
      </template>

      <!-- Nothing saved yet. Always shown, so a missing permission is
           explained rather than leaving the bar without a way to save. -->
      <Button
        v-else
        v-tooltip.bottom="canSave ? '' : t('tools.calculations.actions.saveNoPermission')"
        :label="t('tools.calculations.actions.save')"
        icon="mdi mdi-content-save-outline"
        severity="contrast"
        text
        :disabled="!canSave"
        :loading="saved.busy.value"
        data-testid="calc-save"
        @click="onSave"
      />

      <Divider layout="vertical" />
      <Button
        v-if="calc"
        :label="t('tools.calculations.actions.history')"
        icon="mdi mdi-history"
        severity="contrast"
        text
        data-testid="calc-history"
        @click="historyVisible = true"
      />
      <Button
        v-tooltip.bottom="saved.canPrint.value ? '' : t('tools.calculations.actions.printBlocked')"
        :label="t('tools.calculations.actions.print')"
        icon="mdi mdi-printer-outline"
        severity="contrast"
        text
        :disabled="!saved.canPrint.value"
        data-testid="calc-print"
        @click="emit('print')"
      />

      <!-- The tool itself: start over, open another calculation. -->
      <template v-if="!saved.editing.value">
        <Divider layout="vertical" />
        <Button
          :label="t('tools.calculations.actions.startNew')"
          icon="mdi mdi-plus"
          severity="contrast"
          text
          data-testid="calc-new-tool"
          @click="onNew"
        />
        <Button
          :label="t('tools.calculations.actions.load')"
          icon="mdi mdi-folder-open-outline"
          severity="contrast"
          text
          data-testid="calc-load"
          @click="onLoad"
        />
        <span
          v-if="calc"
          v-tooltip.bottom="saved.canCreate.value ? '' : t('tools.calculations.actions.saveNoPermission')"
        >
          <Button
            :label="t('tools.calculations.actions.saveAsNew')"
            icon="mdi mdi-content-save-plus-outline"
            severity="contrast"
            text
            :disabled="!saved.canCreate.value"
            data-testid="calc-save-as-new"
            @click="openDialog('create')"
          />
        </span>
      </template>
    </template>
    <template #handbook>
      <ShareButton :public-id="calc?.public_id" />
      <HelpButton rounded slug="workspace/document-editing" />
    </template>
  </ControlsBar>

  <Message v-if="saved.loadFailed.value" severity="error" class="calc-message">
    {{ t('tools.calculations.errors.notFound') }}
  </Message>
  <template v-if="calc">
    <DocumentInvalidNotice class="calc-message" :document="calc" />
    <Message v-if="!calc.is_latest && saved.latestRevision.value" severity="info" class="calc-message" data-testid="calc-not-latest">
      {{ t('tools.calculations.notices.notLatest', { revision: saved.latestRevision.value.revision }) }}
      <RouterLink :to="toolPath(tab, saved.latestRevision.value.public_id)">
        {{ t('tools.calculations.notices.openLatest') }}
      </RouterLink>
    </Message>
    <DocumentLockNotice
      v-if="saved.lock.lockedByOther.value"
      class="calc-message"
      :name="saved.lock.lockedByOther.value.name"
      :since="saved.lock.lockedByOther.value.since"
      :can-take-over="saved.canTakeOver.value"
      :take-over-blocked="saved.takeOverBlocked.value"
      :busy="saved.lock.busy.value"
      @take-over="takeOver"
      @end="endEditing"
    />
  </template>
  <CalculationDriftNotice
    v-if="calc && saved.drift.value"
    class="calc-message"
    :differences="saved.differences.value"
    :saved-engine-version="calc.engine_version"
  />

  <SaveCalculationDialog
    v-model:visible="dialogVisible"
    :mode="dialogMode"
    :initial="dialogInitial"
    :busy="saved.busy.value"
    @save="onDialogSave"
  />
  <DocumentReasonDialog
    v-if="calc"
    v-model:visible="reviseVisible"
    :header="t('tools.calculations.revise.title', { revision: calc.revision })"
    :intro="t('tools.calculations.revise.intro', { revision: calc.revision })"
    :submit-label="t('tools.calculations.revise.submit')"
    submit-icon="mdi mdi-file-replace-outline"
    :busy="saved.busy.value"
    @submit="onRevise"
  />
  <DocumentReasonDialog
    v-if="calc"
    v-model:visible="invalidVisible"
    :header="t('documents.invalid.title', { revision: calc.revision })"
    :intro="t('documents.invalid.intro')"
    :submit-label="t('documents.invalid.submit')"
    submit-icon="mdi mdi-cancel"
    severity="danger"
    :busy="saved.busy.value"
    @submit="onMarkInvalid"
  />
  <CalculationHistoryDialog v-if="calc" v-model:visible="historyVisible" :calculation="calc" @open="openRevision" />
  <LoadCalculationDialog v-model:visible="loadVisible" :tool="toolKey" @select="onLoaded" />
  <ConfirmDialog group="tool-calculation" />
</template>

<style scoped lang="scss">
.calc-message {
  margin: var(--space-1) 0;
}
</style>
