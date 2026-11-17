import { computed, reactive, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { LiveResource } from '@/core/realtime/resources'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useControlledDocument } from '@/shared/documents'
import { deleteChecklist } from '../api/deleteChecklist'
import { getChecklist } from '../api/getChecklist'
import { getChecklistRevisions } from '../api/getChecklistRevisions'
import { lockChecklist, unlockChecklist } from '../api/lockChecklist'
import { markChecklistInvalid } from '../api/markChecklistInvalid'
import { releaseChecklist } from '../api/releaseChecklist'
import { reviseChecklist } from '../api/reviseChecklist'
import { updateChecklist } from '../api/updateChecklist'
import type { ChecklistOwner, ChecklistResponse, ChecklistSummaryResponse } from '../types/checklist'
import { CHECKLISTS } from '../utils/definitions'
import { diffChecklists } from '../utils/diff'
import type { ChecklistDiff } from '../utils/diff'
import { countAnswers, findingsWithoutRemark } from '../utils/evaluation'
import { CHECKLIST_DEFINITION_VERSION } from '../utils/index'
import { ownerIds, ownerOf } from '../utils/owner'
import { answersFromRecord, emptyHeader, headerFromRecord, headerToRecord, HEADER_OWNER_FIELDS } from '../utils/state'
import { checklistTitle } from '../utils/title'
import { isChecklistType } from '../utils/types'
import type { Answer, ChecklistDefinition, ChecklistHeader, ChecklistState } from '../utils/types'
import { noOwnerData, useOwnerData } from './useOwnerData'
import type { OwnerData } from './useOwnerData'

/** The unsaved changes of a checklist as this browser keeps them. */
interface ChecklistDraft {
  header: Record<string, string>
  answers: Record<string, string>
  remarks: Record<string, string>
}

/** Why a checklist cannot be released right now, in the order they are shown. */
export type ReleaseBlocker = 'incomplete' | 'remarks' | 'ownRevision'

function sameRecord(a: Readonly<Record<string, string>>, b: Readonly<Record<string, string>>): boolean {
  const keys = Object.keys(a)
  return keys.length === Object.keys(b).length && keys.every((key) => a[key] === b[key])
}

/**
 * One checklist as the detail page edits it: the saved record, the header,
 * answers and remarks on screen, the revision before it (for the changes
 * since then), and what the current user may do with it. Answers to items
 * the checklist type no longer has are dropped on load and counted.
 *
 * A draft is changed only while the user holds its edit lock: Edit takes
 * it, Save keeps it and Discard ends it. Changes by others arrive
 * through the live stream. Unsaved changes are kept in this browser while
 * they exist; when editing ends without them being saved, because the lock
 * was taken over, nobody worked on the page for a while or the page was
 * left, they are offered again, right away or when the checklist is opened
 * next.
 */
export function useChecklistDocument(checklistId: Ref<number>) {
  const { t } = useI18n()
  const translate = (key: string, params?: Record<string, unknown>) => (params ? t(key, params) : t(key))
  const currentUserStore = useCurrentUserStore()
  const ownerData = useOwnerData()

  const checklist = ref<ChecklistResponse | null>(null)
  const revisions = ref<ChecklistSummaryResponse[]>([])
  const previous = ref<ChecklistResponse | null>(null)
  const liveOwner = ref<OwnerData | null>(null)
  const loading = ref(false)
  const loadFailed = ref(false)
  const dropped = ref(0)

  const header = reactive<ChecklistHeader>(emptyHeader())
  const answers = ref<Record<string, Answer>>({})
  const remarks = ref<Record<string, string>>({})

  const definition = computed<ChecklistDefinition | null>(() => {
    const type = checklist.value?.type
    return type && isChecklistType(type) ? CHECKLISTS[type] : null
  })

  function show(loaded: ChecklistResponse): void {
    checklist.value = loaded
    Object.assign(header, headerFromRecord(loaded.header))
    const def = isChecklistType(loaded.type) ? CHECKLISTS[loaded.type] : null
    if (def) {
      const read = answersFromRecord(def, loaded.answers, loaded.remarks)
      answers.value = read.answers
      remarks.value = read.remarks
      dropped.value = read.dropped
    } else {
      answers.value = {}
      remarks.value = {}
      dropped.value = 0
    }
  }

  // The revision right before this one, for the changes since then. It is
  // loaded in full only when there is one.
  async function loadHistory(current: ChecklistResponse): Promise<void> {
    revisions.value = await getChecklistRevisions(current.id)
    const index = revisions.value.findIndex((row) => row.id === current.id)
    const before = index >= 0 ? revisions.value[index + 1] : undefined
    previous.value = before ? await getChecklist(before.id) : null
  }

  // A draft shows its owner as it is now, and takes that into its header on
  // the next save; a read-only checklist shows what it saved.
  async function loadOwner(current: ChecklistResponse): Promise<void> {
    liveOwner.value = null
    if (current.read_only) return
    try {
      liveOwner.value = await ownerData.load(ownerOf(current))
    } catch {
      liveOwner.value = null
    }
  }

  async function load(): Promise<void> {
    const id = checklistId.value
    loading.value = true
    loadFailed.value = false
    try {
      const loaded = await getChecklist(id)
      if (checklistId.value !== id) return
      show(loaded)
      draft.check()
      await Promise.all([loadHistory(loaded), loadOwner(loaded)])
    } catch {
      if (checklistId.value !== id) return
      checklist.value = null
      loadFailed.value = true
    } finally {
      if (checklistId.value === id) loading.value = false
    }
  }

  watch(
    checklistId,
    (id) => {
      // Leaving the route fires this before unmount, when the id is NaN.
      if (Number.isInteger(id)) void load()
    },
    { immediate: true },
  )

  /** The owner fields as the header shows them: live for a draft, saved otherwise. */
  const ownerFields = computed<OwnerData>(() => {
    if (liveOwner.value) return liveOwner.value
    const fields = { ...noOwnerData(), legalBasis: header.legalBasis }
    for (const field of HEADER_OWNER_FIELDS) fields[field] = header[field]
    return fields
  })

  // The checklist as it shows: its own fields as edited, the owner's fields
  // as they are now, so the references follow the product's legal basis.
  const state = computed<ChecklistState>(() => ({
    header: { ...header, ...ownerFields.value },
    answers: answers.value,
    remarks: remarks.value,
  }))

  const headerRecord = computed(() => headerToRecord({ ...header, ...ownerFields.value }))

  const dirty = computed(() => {
    const saved = checklist.value
    const def = definition.value
    if (!saved || !def || saved.read_only) return false
    const savedAnswers = answersFromRecord(def, saved.answers, saved.remarks)
    return (
      !sameRecord(headerToRecord(headerFromRecord(saved.header)), headerToRecord(header)) ||
      !sameRecord(savedAnswers.answers, answers.value) ||
      !sameRecord(savedAnswers.remarks, remarks.value)
    )
  })

  const counts = computed(() => (definition.value ? countAnswers(definition.value.items, answers.value) : null))
  const missingRemarks = computed(() =>
    definition.value ? findingsWithoutRemark(definition.value, state.value) : [],
  )

  /** The changes since the revision before this one, null for a first revision. */
  const changes = computed<ChecklistDiff | null>(() => {
    const def = definition.value
    const before = previous.value
    if (!def || !before) return null
    return diffChecklists(def, before, {
      header: headerRecord.value,
      answers: answers.value,
      remarks: remarks.value,
    })
  })

  // The creator of a revision cannot release it themselves.
  const isOwn = computed(() => checklist.value?.creator_id === (currentUserStore.user?.id ?? null))

  const lifecycle = useControlledDocument<ChecklistResponse, ChecklistDraft, ReleaseBlocker>({
    document: checklist,
    opened: checklistId,
    resource: LiveResource.CHECKLISTS,
    api: {
      get: getChecklist,
      lock: lockChecklist,
      unlock: unlockChecklist,
      release: releaseChecklist,
      markInvalid: markChecklistInvalid,
      revise: reviseChecklist,
      remove: deleteChecklist,
    },
    permissions: {
      write: Permission.WRITE_CHECKLISTS,
      manage: Permission.MANAGE_CHECKLISTS,
      release: Permission.RELEASE_CHECKLISTS,
    },
    // While editing, only the record's lock and release fields move on; the
    // answers on screen are the user's own.
    show,
    draft: {
      name: 'checklist',
      value: () =>
        dirty.value ? { header: headerToRecord(header), answers: answers.value, remarks: remarks.value } : null,
      restorable: () => definition.value !== null,
      restore: (value) => {
        const def = definition.value
        if (!def) return
        Object.assign(header, headerFromRecord(value.header))
        const read = answersFromRecord(def, value.answers, value.remarks)
        answers.value = read.answers
        remarks.value = read.remarks
      },
    },
    offered: {
      // Only a checklist type that asks for a release offers it.
      release: ({ standard }) => standard && !!checklist.value?.release_required,
      // A finished checklist continues in a new revision, released or not.
      revise: ({ editing }) =>
        !!checklist.value && checklist.value.is_latest && checklist.value.finished && !dirty.value && !editing,
    },
    releaseBlockers: () => {
      const blockers: ReleaseBlocker[] = []
      // The answers on screen count, since a release saves them first.
      if (counts.value && counts.value.open > 0) blockers.push('incomplete')
      if (missingRemarks.value.length > 0) blockers.push('remarks')
      if (isOwn.value) blockers.push('ownRevision')
      return blockers
    },
    afterStartEditing: async () => {
      const current = checklist.value
      if (current) await loadOwner(current)
    },
    afterRelease: async (released) => {
      liveOwner.value = null
      await loadHistory(released)
    },
  })
  const { draft, run } = lifecycle

  const canChangeOwner = computed(() => lifecycle.editable.value && revisions.value.length <= 1)
  /** Whether the release action is offered and the user may release; releaseBlockers says why it may be disabled. */
  const showRelease = computed(() => lifecycle.offered.value.release && lifecycle.missing.value.release === null)

  function payload(owner: ChecklistOwner) {
    const def = definition.value
    if (!def) throw new Error('Unknown checklist type.')
    const fullHeader = { ...header, ...ownerFields.value }
    return {
      title: checklistTitle(def.type, fullHeader, translate),
      header: headerToRecord(fullHeader),
      answers: answers.value,
      remarks: remarks.value,
      definition_version: CHECKLIST_DEFINITION_VERSION,
      item_count: def.items.length,
      ...ownerIds(owner),
    }
  }

  async function save(): Promise<void> {
    const current = checklist.value
    if (!current) return
    await run(async () => {
      show(await updateChecklist(current.id, payload(ownerOf(current))))
      revisions.value = await getChecklistRevisions(current.id)
    })
  }

  /** Releases the checklist on screen: unsaved answers are saved first, and the release ends editing. */
  async function release(): Promise<void> {
    if (dirty.value) await save()
    await lifecycle.release()
  }

  /** Moves a single-revision draft to another owner; it is saved at once. */
  async function changeOwner(owner: ChecklistOwner): Promise<void> {
    const current = checklist.value
    if (!current) return
    await run(async () => {
      liveOwner.value = await ownerData.load(owner)
      show(await updateChecklist(current.id, payload(owner)))
    })
  }

  function setAnswer(id: string, value: Answer | null): void {
    const next = { ...answers.value }
    if (value === null) delete next[id]
    else next[id] = value
    answers.value = next
  }

  function setRemark(id: string, value: string): void {
    const next = { ...remarks.value }
    if (value.trim() === '') delete next[id]
    else next[id] = value
    remarks.value = next
  }

  return {
    checklist,
    revisions,
    previous,
    definition,
    header,
    answers,
    remarks,
    state,
    ownerFields,
    dropped,
    loading,
    loadFailed,
    busy: lifecycle.busy,
    dirty,
    counts,
    changes,
    released: lifecycle.released,
    canUpdate: lifecycle.canChange,
    canChangeOwner,
    showRelease,
    offered: lifecycle.offered,
    missing: lifecycle.missing,
    canRelease: lifecycle.canRelease,
    releaseBlockers: lifecycle.releaseBlockers,
    canEdit: lifecycle.canEdit,
    editable: lifecycle.editable,
    canTakeOver: lifecycle.canTakeOver,
    takeOverBlocked: lifecycle.takeOverBlocked,
    canMarkInvalid: lifecycle.canMarkInvalid,
    canRevise: lifecycle.canRevise,
    canDelete: lifecycle.canDelete,
    load,
    save,
    changeOwner,
    release,
    markInvalid: lifecycle.markInvalid,
    startEditing: lifecycle.startEditing,
    discard: lifecycle.discard,
    lock: lifecycle.lock,
    lostBy: lifecycle.lostBy,
    idleEnded: lifecycle.idleEnded,
    draft,
    draftBlocked: lifecycle.draftBlocked,
    restoreDraft: lifecycle.restoreDraft,
    revise: lifecycle.revise,
    remove: lifecycle.remove,
    setAnswer,
    setRemark,
  }
}

export type ChecklistDocument = ReturnType<typeof useChecklistDocument>
