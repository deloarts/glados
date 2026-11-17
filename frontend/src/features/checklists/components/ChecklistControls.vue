<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ShareButton from '@/shared/components/resource-view/ShareButton.vue'
import { HelpButton } from '@/shared/help'
import type { DocumentAction } from '@/shared/documents'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import type { ChecklistDocument } from '../composables/useChecklistDocument'

/**
 * The actions on one checklist. Outside editing: Release, Edit, New
 * Revision, Mark as Invalid and Delete, as far as the checklist's state
 * allows them; one the user lacks the rights for is shown disabled with the
 * missing permission. While editing: Save, Release (which saves the
 * changes first and ends editing), Done, which reads Discard and asks first
 * while there are unsaved changes, Delete and the owner of a single draft. Compare, History and Print follow after a divider in both. Release
 * is also shown disabled with the reason while the checklist cannot be
 * released yet.
 */

const props = defineProps<{ doc: ChecklistDocument }>()

const emit = defineEmits<{
  print: []
  compare: []
  history: []
  revise: []
  owner: []
  invalidate: []
  deleted: []
}>()

const { t } = useI18n()
const toast = useAppToast()
const confirm = useConfirm()

const checklist = computed(() => props.doc.checklist.value)
const hasHistory = computed(() => props.doc.revisions.value.length > 1)

async function attempt(action: () => Promise<unknown>, success: string): Promise<boolean> {
  try {
    await action()
    toast.success(checklist.value?.title ?? t('checklists.title'), success)
    return true
  } catch (e) {
    toast.error(checklist.value?.title ?? t('checklists.title'), extractApiError(e) ?? t('checklists.errors.unknown'))
    return false
  }
}

function save(): void {
  void attempt(props.doc.save, t('checklists.toasts.saved'))
}

/** Why an offered button cannot be pressed: the permission the user lacks. */
function blockedBy(action: DocumentAction): string {
  const permission = props.doc.missing.value[action]
  return permission ? t('documents.permissionMissing', { permission: permissionLabel(t, permission) }) : ''
}

const releaseTooltip = computed(() =>
  [blockedBy('release'), ...props.doc.releaseBlockers.value.map((b) => t(`checklists.releaseBlocked.${b}`))]
    .filter(Boolean)
    .join(' '),
)

function edit(): void {
  props.doc.startEditing().catch((e: unknown) => {
    toast.error(checklist.value?.title ?? t('checklists.title'), extractApiError(e) ?? t('checklists.errors.unknown'))
  })
}

function finish(): void {
  if (!props.doc.dirty.value) {
    void props.doc.discard()
    return
  }
  confirm.require({
    group: 'checklist-controls',
    header: t('documents.lock.discard'),
    message: t('documents.lock.discardConfirm'),
    icon: 'mdi mdi-alert-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('documents.lock.discard'), severity: 'danger' },
    accept: () => void props.doc.discard(),
  })
}

type ConfirmKey = 'release' | 'delete'

function ask(key: ConfirmKey, action: () => unknown): void {
  const saveFirst = key === 'release' && props.doc.dirty.value
  confirm.require({
    group: 'checklist-controls',
    header: t(`checklists.confirm.${key}.header`),
    message: [t(`checklists.confirm.${key}.message`), saveFirst ? t('checklists.confirm.release.saveFirst') : '']
      .filter(Boolean)
      .join(' '),
    icon: key === 'release' ? 'mdi mdi-check-decagram-outline' : 'mdi mdi-alert-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: {
      label: t(`checklists.confirm.${key}.accept`),
      severity: key === 'delete' ? 'danger' : 'primary',
    },
    accept: action,
  })
}

async function remove(): Promise<void> {
  if (await attempt(props.doc.remove, t('checklists.toasts.delete'))) emit('deleted')
}

/** Releases like the button does; false when the checklist cannot be released now. */
function release(): boolean {
  if (!props.doc.canRelease.value) return false
  ask('release', () => attempt(props.doc.release, t('checklists.toasts.release')))
  return true
}

// The page starts these for a list's row menu.
defineExpose({
  edit: (): boolean => {
    if (!props.doc.canEdit.value) return false
    edit()
    return true
  },
  release,
})
</script>

<template>
  <ControlsBar data-testid="cl-controls">
    <template #start>
      <template v-if="doc.editable.value">
        <Button
          :label="t('checklists.actions.save')"
          icon="mdi mdi-content-save-outline"
          severity="contrast"
          text
          :disabled="!doc.dirty.value"
          :loading="doc.busy.value"
          data-testid="cl-save"
          @click="save"
        />
        <span v-if="doc.offered.value.release" v-tooltip.bottom="releaseTooltip">
          <Button
            :label="t('checklists.actions.release')"
            icon="mdi mdi-check-decagram-outline"
            severity="contrast"
            text
            :disabled="!doc.canRelease.value || doc.busy.value"
            data-testid="cl-release"
            @click="ask('release', () => attempt(doc.release, t('checklists.toasts.release')))"
          />
        </span>
        <Button
          :label="doc.dirty.value ? t('documents.lock.discard') : t('checklists.actions.done')"
          :icon="doc.dirty.value ? 'mdi mdi-close-circle-outline' : 'mdi mdi-check'"
          severity="contrast"
          text
          :loading="doc.lock.busy.value"
          data-testid="cl-finish"
          @click="finish"
        />
        <span v-if="doc.offered.value.delete" v-tooltip.bottom="blockedBy('delete')">
          <Button
            :label="t('common.delete')"
            icon="mdi mdi-delete-outline"
            severity="contrast"
            text
            :disabled="!doc.canDelete.value"
            data-testid="cl-delete"
            @click="ask('delete', remove)"
          />
        </span>
        <Button
          v-if="doc.canChangeOwner.value"
          :label="t('checklists.actions.owner')"
          icon="mdi mdi-swap-horizontal"
          severity="contrast"
          text
          data-testid="cl-owner"
          @click="emit('owner')"
        />
      </template>
      <template v-else>
        <span v-if="doc.offered.value.release" v-tooltip.bottom="releaseTooltip">
          <Button
            :label="t('checklists.actions.release')"
            icon="mdi mdi-check-decagram-outline"
            severity="contrast"
            text
            :disabled="!doc.canRelease.value || doc.busy.value"
            data-testid="cl-release"
            @click="ask('release', () => attempt(doc.release, t('checklists.toasts.release')))"
          />
        </span>
        <span v-if="doc.offered.value.edit" v-tooltip.bottom="blockedBy('edit')">
          <Button
            :label="t('documents.lock.edit')"
            icon="mdi mdi-pencil-outline"
            severity="contrast"
            text
            :disabled="!doc.canEdit.value"
            :loading="doc.lock.busy.value"
            data-testid="cl-edit"
            @click="edit"
          />
        </span>
        <span v-if="doc.offered.value.revise" v-tooltip.bottom="blockedBy('revise')">
          <Button
            :label="t('checklists.actions.revise')"
            icon="mdi mdi-file-replace-outline"
            severity="contrast"
            text
            :disabled="!doc.canRevise.value"
            data-testid="cl-revise"
            @click="emit('revise')"
          />
        </span>
        <span v-if="doc.offered.value.invalidate" v-tooltip.bottom="blockedBy('invalidate')">
          <Button
            :label="t('documents.invalid.action')"
            icon="mdi mdi-cancel"
            severity="contrast"
            text
            :disabled="!doc.canMarkInvalid.value"
            data-testid="cl-mark-invalid"
            @click="emit('invalidate')"
          />
        </span>
        <span v-if="doc.offered.value.delete" v-tooltip.bottom="blockedBy('delete')">
          <Button
            :label="t('common.delete')"
            icon="mdi mdi-delete-outline"
            severity="contrast"
            text
            :disabled="!doc.canDelete.value"
            data-testid="cl-delete"
            @click="ask('delete', remove)"
          />
        </span>
      </template>
      <Divider layout="vertical" />
      <Button
        v-if="hasHistory"
        :label="t('checklists.actions.compare')"
        icon="mdi mdi-compare-horizontal"
        severity="contrast"
        text
        data-testid="cl-compare"
        @click="emit('compare')"
      />
      <Button
        :label="t('checklists.actions.history')"
        icon="mdi mdi-history"
        severity="contrast"
        text
        data-testid="cl-history"
        @click="emit('history')"
      />
      <Button
        v-tooltip.bottom="doc.dirty.value ? t('checklists.actions.printBlocked') : ''"
        :label="t('checklists.actions.print')"
        icon="mdi mdi-printer-outline"
        severity="contrast"
        text
        :disabled="doc.dirty.value"
        data-testid="cl-print"
        @click="emit('print')"
      />
    </template>
    <template #handbook>
      <ShareButton :public-id="doc.checklist.value?.public_id" />
      <HelpButton rounded slug="workspace/document-editing" />
    </template>
  </ControlsBar>
  <ConfirmDialog group="checklist-controls" />
</template>
