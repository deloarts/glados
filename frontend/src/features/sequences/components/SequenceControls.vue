<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useConfirm } from 'openvue/useconfirm'

import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import { HelpButton } from '@/shared/help'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ShareButton from '@/shared/components/resource-view/ShareButton.vue'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import type { SequenceAction, SequenceDocument } from '../composables/useSequenceDocument'

/**
 * The actions on one sequence, laid out like a checklist's, after Back to
 * Sequences, which returns to the product's sequences tab. Outside
 * editing: Release, Edit, New Revision, Mark as Invalid and Delete, as far
 * as the sequence's state allows them; one the user lacks the rights for
 * is shown disabled with the missing permission. While editing: Save,
 * Release (which saves the changes first and ends editing), Done, which
 * reads Discard and asks first while there are unsaved changes, and
 * Delete. History follows after a divider. Release is also shown disabled
 * with the reason while the sequence cannot be released yet. How the
 * sequence is looked at lives in SequenceViews.
 */
const props = defineProps<{ doc: SequenceDocument }>()

const emit = defineEmits<{
  history: []
  revise: []
  invalidate: []
  deleted: []
}>()

const { t } = useI18n()
const router = useRouter()
const toast = useAppToast()
const confirm = useConfirm()

const sequence = computed(() => props.doc.sequence.value)

// Unsaved steps are guarded by the page, which asks before leaving.
function back(): void {
  const current = sequence.value
  if (current) void router.push({ name: 'ProductDetail', params: { id: current.product_id, tab: 'sequences' } })
}

async function attempt(action: () => Promise<unknown>, success: string): Promise<boolean> {
  try {
    await action()
    toast.success(sequence.value?.name ?? t('sequences.title'), success)
    return true
  } catch (e) {
    toast.error(sequence.value?.name ?? t('sequences.title'), extractApiError(e) ?? t('sequences.errors.unknown'))
    return false
  }
}

function save(): void {
  void attempt(props.doc.save, t('sequences.toasts.saved'))
}

/** Why an offered button cannot be pressed: the permission the user lacks. */
function blockedBy(action: SequenceAction): string {
  const permission = props.doc.missing.value[action]
  return permission ? t('sequences.permissionMissing', { permission: permissionLabel(t, permission) }) : ''
}

// While editing, the handbook explains building the steps; otherwise the
// bar offers editing, release and revisions, which have a page of their own.
const handbookSlug = computed(() =>
  props.doc.editable.value ? 'workspace/flow-sequences' : 'workspace/flow-sequence-release',
)

const releaseTooltip = computed(() =>
  [blockedBy('release'), ...props.doc.releaseBlockers.value.map((b) => t(`sequences.releaseBlocked.${b}`))]
    .filter(Boolean)
    .join(' '),
)

function edit(): void {
  props.doc.startEditing().catch((e: unknown) => {
    toast.error(sequence.value?.name ?? t('sequences.title'), extractApiError(e) ?? t('sequences.errors.unknown'))
  })
}

function finish(): void {
  if (!props.doc.dirty.value) {
    void props.doc.discard()
    return
  }
  confirm.require({
    group: 'sequence-controls',
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
    group: 'sequence-controls',
    header: t(`sequences.confirm.${key}.header`),
    message: [t(`sequences.confirm.${key}.message`), saveFirst ? t('sequences.confirm.release.saveFirst') : '']
      .filter(Boolean)
      .join(' '),
    icon: key === 'release' ? 'mdi mdi-check-decagram-outline' : 'mdi mdi-alert-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: {
      label: t(`sequences.confirm.${key}.accept`),
      severity: key === 'delete' ? 'danger' : 'primary',
    },
    accept: action,
  })
}

async function remove(): Promise<void> {
  if (await attempt(props.doc.remove, t('sequences.toasts.deleted'))) emit('deleted')
}

/** Releases like the button does; false when the sequence cannot be released now. */
function release(): boolean {
  if (!props.doc.canRelease.value) return false
  ask('release', () => attempt(props.doc.release, t('sequences.toasts.released')))
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
  <ControlsBar data-testid="sequence-controls">
    <template #start>
      <Button
        :label="t('sequences.actions.back')"
        icon="mdi mdi-arrow-left"
        severity="contrast"
        text
        data-testid="sequence-back"
        @click="back"
      />
      <Divider layout="vertical" />
      <template v-if="doc.editable.value">
        <Button
          :label="t('common.save')"
          icon="mdi mdi-content-save-outline"
          severity="contrast"
          text
          :disabled="!doc.dirty.value"
          :loading="doc.busy.value"
          data-testid="sequence-save"
          @click="save"
        />
        <span v-if="doc.offered.value.release" v-tooltip.bottom="releaseTooltip">
          <Button
            :label="t('sequences.actions.release')"
            icon="mdi mdi-check-decagram-outline"
            severity="contrast"
            text
            :disabled="!doc.canRelease.value || doc.busy.value"
            data-testid="sequence-release"
            @click="release"
          />
        </span>
        <Button
          :label="doc.dirty.value ? t('documents.lock.discard') : t('sequences.actions.done')"
          :icon="doc.dirty.value ? 'mdi mdi-close-circle-outline' : 'mdi mdi-check'"
          severity="contrast"
          text
          :loading="doc.lock.busy.value"
          data-testid="sequence-finish"
          @click="finish"
        />
      </template>
      <template v-else>
        <span v-if="doc.offered.value.release" v-tooltip.bottom="releaseTooltip">
          <Button
            :label="t('sequences.actions.release')"
            icon="mdi mdi-check-decagram-outline"
            severity="contrast"
            text
            :disabled="!doc.canRelease.value || doc.busy.value"
            data-testid="sequence-release"
            @click="release"
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
            data-testid="sequence-edit"
            @click="edit"
          />
        </span>
        <span v-if="doc.offered.value.revise" v-tooltip.bottom="blockedBy('revise')">
          <Button
            :label="t('sequences.actions.revise')"
            icon="mdi mdi-file-replace-outline"
            severity="contrast"
            text
            :disabled="!doc.canRevise.value"
            data-testid="sequence-revise"
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
            data-testid="sequence-mark-invalid"
            @click="emit('invalidate')"
          />
        </span>
      </template>
      <span v-if="doc.offered.value.delete" v-tooltip.bottom="blockedBy('delete')">
        <Button
          :label="t('common.delete')"
          icon="mdi mdi-delete-outline"
          severity="contrast"
          text
          :disabled="!doc.canDelete.value"
          data-testid="sequence-delete"
          @click="ask('delete', remove)"
        />
      </span>
      <Divider layout="vertical" />
      <Button
        :label="t('sequences.actions.history')"
        icon="mdi mdi-history"
        severity="contrast"
        text
        data-testid="sequence-history"
        @click="emit('history')"
      />
    </template>
    <template #handbook>
      <ShareButton :public-id="doc.sequence.value?.public_id" />
      <HelpButton rounded :slug="handbookSlug" />
    </template>
  </ControlsBar>
  <ConfirmDialog group="sequence-controls" />
</template>
