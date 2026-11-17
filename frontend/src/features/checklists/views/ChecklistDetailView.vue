<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useConfirm } from 'openvue/useconfirm'

import { useAppToast } from '@/core/composables/useAppToast'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePageTitle } from '@/core/composables/usePageTitle'
import { formatISODateTime } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { HelpButton } from '@/shared/help'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import { useConfirmAsync } from '@/shared/composables/useConfirmAsync'
import { useLeaveGuard } from '@/shared/composables/useLeaveGuard'
import {
  DocumentDraftDialog,
  DocumentInvalidNotice,
  DocumentLockNotice,
  DocumentReasonDialog,
  useDocumentPageAction,
} from '@/shared/documents'
import type { DocumentPageAction } from '@/shared/documents'
import { ReportExportDialog, useReportExport } from '@/shared/reports'
import ChecklistControls from '../components/ChecklistControls.vue'
import ChecklistEditor from '../components/ChecklistEditor.vue'
import ChecklistHistoryDialog from '../components/ChecklistHistoryDialog.vue'
import ChecklistInfo from '../components/ChecklistInfo.vue'
import ChecklistOwnerDialog from '../components/ChecklistOwnerDialog.vue'
import ReviseChecklistDialog from '../components/ReviseChecklistDialog.vue'
import { useChecklistDocument } from '../composables/useChecklistDocument'
import type { ChecklistOwner } from '../types/checklist'
import { ownerLink, ownerOf } from '../utils/owner'
import { checklistReportSpec } from '../utils/report'

/**
 * /checklists/:id, one revision of a checklist. The latest, unreleased
 * revision is filled in here after Edit takes its lock; a released or older
 * one, or one somebody else is editing, is shown read-only. Items changed
 * since the revision before are marked.
 */

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useAppToast()
const confirm = useConfirm()
const { ask } = useConfirmAsync()

const checklistId = computed(() => Number(route.params.id))
const doc = useChecklistDocument(checklistId)
watchLoadingBar(doc.loading)

const checklist = computed(() => doc.checklist.value)
const owner = computed<ChecklistOwner>(() => (checklist.value ? ownerOf(checklist.value) : { kind: 'personal' }))
const readOnly = computed(() => !doc.editable.value)

const releasedBy = computed(() => {
  const c = checklist.value
  if (!c?.released_at) return null
  return `${c.released_by_full_name ?? ''}, ${formatISODateTime(c.released_at)}`
})

/** The newest revision, linked from an older one. */
const latest = computed(() => doc.revisions.value[0] ?? null)
const previousRevision = computed(() => doc.previous.value?.revision ?? null)

const reviseVisible = ref(false)
const ownerVisible = ref(false)
const historyVisible = ref(false)
const invalidVisible = ref(false)

async function onMarkInvalid(reason: string): Promise<void> {
  try {
    await doc.markInvalid(reason)
    invalidVisible.value = false
    toast.success(checklist.value?.title ?? t('checklists.title'), t('documents.invalid.done'))
  } catch (e) {
    toast.error(checklist.value?.title ?? t('checklists.title'), extractApiError(e) ?? t('checklists.errors.unknown'))
  }
}

// Taking over drops the other editor's unsaved changes, so it asks first.
function takeOver(): void {
  const by = doc.lock.lockedByOther.value?.name ?? ''
  confirm.require({
    group: 'checklist-leave',
    header: t('documents.lock.takeOver'),
    message: t('documents.lock.takeOverConfirm', { name: by }),
    icon: 'mdi mdi-alert-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('documents.lock.takeOver'), severity: 'warn' },
    accept: () => {
      doc.startEditing(true).catch((e: unknown) => {
        toast.error(checklist.value?.title ?? t('checklists.title'), extractApiError(e) ?? t('checklists.errors.unknown'))
      })
    },
  })
}

function endEditing(): void {
  const by = doc.lock.lockedByOther.value?.name ?? ''
  confirm.require({
    group: 'checklist-leave',
    header: t('documents.lock.end'),
    message: t('documents.lock.endConfirm', { name: by }),
    icon: 'mdi mdi-alert-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('documents.lock.end'), severity: 'warn' },
    accept: () => {
      doc.lock.endOthersEditing().catch((e: unknown) => {
        toast.error(checklist.value?.title ?? t('checklists.title'), extractApiError(e) ?? t('checklists.errors.unknown'))
      })
    },
  })
}

watch(
  () => doc.lostBy.value.length,
  () => {
    const by = doc.lostBy.value.at(-1)
    toast.warn(
      checklist.value?.title ?? t('checklists.title'),
      by ? t('documents.lock.lost', { name: by }) : t('documents.lock.lostUnknown'),
    )
  },
)

async function onRevise(reason: string): Promise<void> {
  try {
    const created = await doc.revise(reason)
    reviseVisible.value = false
    if (!created) return
    toast.success(created.title, t('checklists.toasts.revised', { revision: created.revision }))
    await router.push({ name: 'ChecklistDetail', params: { id: created.id } })
  } catch (e) {
    toast.error(checklist.value?.title ?? t('checklists.title'), extractApiError(e) ?? t('checklists.errors.unknown'))
  }
}

async function onOwner(_type: unknown, next: ChecklistOwner): Promise<void> {
  try {
    await doc.changeOwner(next)
    ownerVisible.value = false
    toast.success(checklist.value?.title ?? t('checklists.title'), t('checklists.toasts.saved'))
  } catch (e) {
    toast.error(checklist.value?.title ?? t('checklists.title'), extractApiError(e) ?? t('checklists.errors.unknown'))
  }
}

const { visible: reportVisible, report, open: openReport } = useReportExport()

// Print is offered without unsaved changes only, so the report shows the
// revision as it is stored.
function print(): void {
  const spec = checklist.value && checklistReportSpec(checklist.value)
  if (spec) openReport(spec)
}

function compare(baseId?: number): void {
  historyVisible.value = false
  const base = baseId ?? doc.previous.value?.id
  void router.push({
    name: 'ChecklistCompare',
    params: { id: checklistId.value },
    query: base ? { base: String(base) } : {},
  })
}

function openRevision(id: number): void {
  historyVisible.value = false
  void router.push({ name: 'ChecklistDetail', params: { id } })
}

// Leaving with unsaved answers asks first, also for another revision of the
// same checklist. The answers stay on this device either way.
const leaveGuard = useLeaveGuard({
  dirty: () => doc.dirty.value,
  updates: true,
  confirm: () =>
    ask({
      group: 'checklist-leave',
      header: t('documents.leave.header'),
      message: t('documents.leave.message'),
      icon: 'mdi mdi-alert-outline',
      rejectProps: { label: t('common.cancel'), severity: 'secondary' },
      acceptProps: { label: t('documents.leave.accept'), severity: 'warn' },
    }),
})

// After deleting a revision the one before it is the latest again; without
// one the page goes back to where the checklist belonged. A deleted
// checklist has nothing left to lose.
async function onDeleted(): Promise<void> {
  const before = doc.previous.value
  leaveGuard.allowNext()
  if (before) {
    await router.replace({ name: 'ChecklistDetail', params: { id: before.id } })
    return
  }
  await router.replace(ownerLink(owner.value) ?? '/checklists')
}

const controls = ref<InstanceType<typeof ChecklistControls> | null>(null)

// A list's row menu leaves these steps to the page, which starts them like
// its own buttons do once the checklist is loaded.
useDocumentPageAction({
  ready: () => !!checklist.value && !doc.loading.value && controls.value !== null,
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

watch(
  () => doc.idleEnded.value,
  () => toast.warn(checklist.value?.title ?? t('checklists.title'), t('documents.lock.idle')),
)

async function onRestoreDraft(): Promise<void> {
  try {
    await doc.restoreDraft()
    toast.success(checklist.value?.title ?? t('checklists.title'), t('documents.draft.restored'))
  } catch (e) {
    toast.error(checklist.value?.title ?? t('checklists.title'), extractApiError(e) ?? t('checklists.errors.unknown'))
  }
}

const { setPageTitle } = usePageTitle()
watch(
  () => checklist.value?.title ?? t('checklists.title'),
  (title) => setPageTitle(title),
  { immediate: true },
)
</script>

<template>
  <PageLayout :card="false" data-class="cl-view-data">
    <template #info>
      <ChecklistInfo :doc="doc" />
    </template>
    <template v-if="checklist" #controls>
      <ChecklistControls
        ref="controls"
        :doc="doc"
        @print="print"
        @compare="compare()"
        @history="historyVisible = true"
        @revise="reviseVisible = true"
        @owner="ownerVisible = true"
        @invalidate="invalidVisible = true"
        @deleted="onDeleted"
      />
    </template>

    <div v-if="doc.loadFailed.value" class="state-message">
      <i class="mdi mdi-alert-circle-outline state-icon" aria-hidden="true" />
      <span>{{ t('checklists.errors.notFound') }}</span>
    </div>

    <div v-else-if="checklist" class="detail">
      <Message v-if="!doc.definition.value" severity="error">{{ t('checklists.errors.unknownType') }}</Message>
      <DocumentInvalidNotice :document="checklist" />
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
      <Message v-if="doc.dropped.value > 0" severity="warn" data-testid="cl-dropped">
        {{ t('checklists.notices.dropped', { count: doc.dropped.value }) }}
      </Message>
      <Message v-if="!checklist.is_latest && latest" severity="info" data-testid="cl-not-latest">
        {{ t('checklists.notices.notLatest', { revision: latest.revision }) }}
        <RouterLink :to="{ name: 'ChecklistDetail', params: { id: latest.id } }">
          {{ t('checklists.notices.openLatest') }}
        </RouterLink>
      </Message>
      <Message v-if="doc.changes.value && previousRevision" severity="secondary" data-testid="cl-changes-since">
        {{ t('checklists.notices.changesSince', { revision: previousRevision, count: doc.changes.value.items.length }) }}
      </Message>

      <ChecklistEditor
        v-if="doc.definition.value"
        :definition="doc.definition.value"
        :state="doc.state.value"
        :owner="owner"
        :owner-fields="doc.ownerFields.value"
        :read-only="readOnly"
        :release-required="checklist.release_required"
        :released-by="releasedBy"
        :changed-ids="doc.changes.value?.changedIds ?? null"
        @answer="doc.setAnswer"
        @remark="doc.setRemark"
        @header="(field, value) => (doc.header[field] = value)"
      />
    </div>

    <ReviseChecklistDialog
      v-if="checklist"
      v-model:visible="reviseVisible"
      :revision="checklist.revision"
      :busy="doc.busy.value"
      @revise="onRevise"
    />
    <DocumentReasonDialog
      v-if="checklist"
      v-model:visible="invalidVisible"
      :header="t('documents.invalid.title', { revision: checklist.revision })"
      :intro="t('documents.invalid.intro')"
      :submit-label="t('documents.invalid.submit')"
      submit-icon="mdi mdi-cancel"
      severity="danger"
      :busy="doc.busy.value"
      @submit="onMarkInvalid"
    />
    <ChecklistOwnerDialog
      v-if="checklist"
      v-model:visible="ownerVisible"
      mode="owner"
      :initial-owner="owner"
      :type="doc.definition.value?.type"
      :busy="doc.busy.value"
      @save="onOwner"
    />
    <ChecklistHistoryDialog
      v-if="checklist"
      v-model:visible="historyVisible"
      :revisions="doc.revisions.value"
      :current-id="checklist.id"
      :public-id="checklist.public_id"
      @open="openRevision"
      @compare="compare"
    />
    <ConfirmDialog group="checklist-leave" />
    <DocumentDraftDialog
      :offer="doc.draft.offer.value"
      :blocked="doc.draftBlocked.value"
      :saved-since="checklist?.changed ?? null"
      :busy="doc.lock.busy.value"
      @restore="onRestoreDraft"
      @discard="doc.draft.discard()"
      @dismiss="doc.draft.dismiss()"
    />
    <ReportExportDialog v-model:visible="reportVisible" :report="report">
      <template #handbook>
        <HelpButton slug="resources/report-export" icon="mdi mdi-help" rounded />
      </template>
    </ReportExportDialog>
  </PageLayout>
</template>

<style scoped lang="scss">
.detail {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);

  > :not(.cl) {
    flex-shrink: 0;
  }

  > .cl {
    flex: 1 1 auto;
  }
}

// The checklist scrolls in its own columns, never the page.
:deep(.cl-view-data) {
  overflow: hidden;
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
