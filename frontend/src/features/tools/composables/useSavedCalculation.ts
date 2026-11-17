import { computed, ref, shallowRef, toRaw, watch } from 'vue'
import type { Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { LiveResource } from '@/core/realtime/resources'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useConfirmAsync } from '@/shared/composables/useConfirmAsync'
import { useLeaveGuard } from '@/shared/composables/useLeaveGuard'
import {
  LOCAL_DRAFT_WRITE_MS,
  readLocalDraft,
  removeLocalDraft,
  useControlledDocument,
  writeLocalDraft,
} from '@/shared/documents'
import { createCalculation } from '../api/createCalculation'
import { deleteCalculation } from '../api/deleteCalculation'
import { getCalculation } from '../api/getCalculation'
import { getCalculationByPublicId } from '../api/getCalculationByPublicId'
import { getCalculationRevisions } from '../api/getCalculationRevisions'
import { lockCalculation, unlockCalculation } from '../api/lockCalculation'
import { markCalculationInvalid } from '../api/markCalculationInvalid'
import { releaseCalculation } from '../api/releaseCalculation'
import { reviseCalculation } from '../api/reviseCalculation'
import { updateCalculation } from '../api/updateCalculation'
import { toolByKey, toolByTab } from '../registry'
import type { CalculationOwner, CalculationResponse, CalculationSummaryResponse } from '../types/calculation'
import { inputsEqual, resultDifferences } from '../utils/calculationCompare'
import type { ToolState } from './useToolState'

export interface CalculationMeta {
  owner: CalculationOwner
  title: string
  note: string | null
  // A device of the owning product, or of the owning project's product.
  deviceId: number | null
}

function ownerIds(owner: CalculationOwner) {
  return {
    project_id: owner.kind === 'project' ? owner.id : null,
    product_id: owner.kind === 'product' ? owner.id : null,
  }
}

export function ownerOf(calculation: CalculationResponse): CalculationOwner {
  if (calculation.project_id !== null) {
    return { kind: 'project', id: calculation.project_id, label: calculation.project_number ?? '' }
  }
  if (calculation.product_id !== null) {
    return { kind: 'product', id: calculation.product_id, label: calculation.product_number ?? '' }
  }
  return { kind: 'personal' }
}

const PUBLIC_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function calcParam(value: unknown): string | null {
  return typeof value === 'string' && PUBLIC_ID.test(value) ? value.toLowerCase() : null
}

/** The tools route of a calculation, or of an unsaved tool when `publicId` is null. */
export function toolPath(tab: string, publicId: string | null): string {
  return publicId ? `/tools/${tab}/${publicId}` : `/tools/${tab}`
}

/**
 * The saved calculation the tools view is showing, if any. It is named by its
 * public id in the route (`/tools/<tool>/<public id>`); its inputs are handed
 * to the tool through `initialInputs`, never through the URL. `resolving`
 * stays true while it loads, and `mountKey` changes whenever a calculation is
 * loaded from the server, so the view remounts the tool on its inputs.
 *
 * A saved draft is changed in place only while the user holds its edit
 * lock (Edit, then Save or Discard); without it the tool still
 * calculates, and Save keeps the figures as a new calculation. A released
 * calculation continues in a new revision or a copy.
 *
 * Nothing on screen is lost by leaving. Unsaved changes of a saved
 * calculation are kept in this browser and offered again when it is opened
 * next; leaving it asks first. A tool without a saved calculation keeps its
 * inputs as a scratch copy per tool and starts on them again, until New
 * clears them or Save turns them into a calculation.
 */
export function useSavedCalculation(activeTab: Ref<string>, state: Ref<ToolState | null>) {
  const route = useRoute()
  const router = useRouter()
  const { hasPermission } = usePermissions()
  const currentUserStore = useCurrentUserStore()
  const { ask } = useConfirmAsync()
  const { t } = useI18n()

  const calculation = ref<CalculationResponse | null>(null)
  const resolving = ref(false)
  const loadFailed = ref(false)
  const mountKey = ref(0)
  // Kept changes put back on screen; the tool mounts on them instead of the saved inputs.
  const restoredInputs = ref<Record<string, string> | null>(null)
  // The tool's inputs from a scratch copy, for a tool opened without a calculation.
  const scratchInputs = ref<Record<string, string> | null>(null)

  /** Mounts the tool afresh, on kept changes when given, else on what it is opened with. */
  function remount(restored: Record<string, string> | null = null): void {
    restoredInputs.value = restored
    mountKey.value += 1
  }

  const publicId = computed(() => calcParam(route.params.calc))

  async function resolve(id: string | null): Promise<void> {
    loadFailed.value = false
    if (id === null) {
      calculation.value = null
      return
    }
    if (calculation.value?.public_id === id) return
    resolving.value = true
    try {
      const loaded = await getCalculationByPublicId(id)
      calculation.value = loaded
      remount()
      draft.check()
      const tool = toolByKey(loaded.tool)
      if (tool && tool.tab !== activeTab.value) {
        await router.replace(toolPath(tool.tab, loaded.public_id))
      }
    } catch {
      calculation.value = null
      loadFailed.value = true
    } finally {
      resolving.value = false
    }
  }

  watch(publicId, resolve, { immediate: true })

  /** All revisions of the open calculation, newest first, loaded for an older revision. */
  const revisions = ref<CalculationSummaryResponse[]>([])
  watch(
    () => calculation.value && { id: calculation.value.id, latest: calculation.value.is_latest },
    async (open) => {
      revisions.value = []
      if (open && !open.latest) revisions.value = await getCalculationRevisions(open.id).catch(() => [])
    },
  )
  const latestRevision = computed(() => revisions.value[0] ?? null)

  /** What the tool starts on when it mounts: kept changes, the open calculation's inputs or its scratch copy. */
  const initialInputs = computed(() => {
    if (!calculation.value) return scratchInputs.value
    return restoredInputs.value ?? (calculation.value.inputs as Record<string, string>)
  })

  const tool = computed(() => toolByTab(activeTab.value))

  // While a tool is being replaced, the one leaving may still hold the
  // published state. Its inputs belong to neither the next tool nor the
  // next calculation, so they are not taken for changes or kept.
  const foreignState = shallowRef<ToolState | null>(null)
  watch(
    [mountKey, () => tool.value?.key],
    () => {
      foreignState.value = state.value ? toRaw(state.value) : null
    },
    { flush: 'sync' },
  )
  const ownState = computed(() => {
    const s = state.value
    return s && toRaw(s) !== foreignState.value ? s : null
  })
  /** Whether the tool on screen has published what it shows, so changes and drift are known. */
  const toolReady = computed(() => ownState.value !== null)

  // The inputs the mounted tool started with, the reference for "changed
  // since it was opened" when nothing is saved yet.
  const baseline = ref<Record<string, string> | null>(null)

  watch([mountKey, () => tool.value?.key], () => (baseline.value = null))
  watch(
    () => ownState.value?.inputs,
    (inputs) => {
      if (inputs && baseline.value === null) baseline.value = { ...inputs }
    },
  )

  // Only a calculation of the tool on screen counts; while a link to another
  // tool is being resolved the old tool may still be mounted for a moment.
  const current = computed(() =>
    calculation.value && calculation.value.tool === tool.value?.key ? calculation.value : null,
  )

  const dirty = computed(() => {
    const calc = current.value
    const s = ownState.value
    return !!calc && !!s && !inputsEqual(s.inputs, calc.inputs)
  })

  /** Puts the kept changes of the open calculation back into the tool. */
  function restoreDraft(): void {
    const value = draft.accept()
    if (value) remount(value.inputs)
  }

  // ── Scratch copy of a tool without a calculation ────────────────────

  const userId = computed(() => currentUserStore.user?.id ?? null)
  const scratchKey = (toolKey: string): string => `calculation.new.${toolKey}`

  // Read before the tool mounts, so it starts on its scratch copy.
  watch(
    [() => tool.value?.key, () => calculation.value === null && publicId.value === null, userId],
    ([toolKey, scratch, uid]) => {
      scratchInputs.value =
        toolKey && scratch && uid !== null
          ? (readLocalDraft<Record<string, string>>(uid, scratchKey(toolKey))?.value ?? null)
          : null
    },
    { immediate: true },
  )

  let scratchTimer: ReturnType<typeof setTimeout> | null = null
  watch(
    () => ownState.value?.inputs,
    (inputs) => {
      const toolKey = tool.value?.key
      const uid = userId.value
      if (!inputs || !toolKey || !tool.value?.saveable || uid === null || calculation.value) return
      const copy = { ...inputs }
      if (scratchTimer) clearTimeout(scratchTimer)
      scratchTimer = setTimeout(() => writeLocalDraft(uid, scratchKey(toolKey), copy, null), LOCAL_DRAFT_WRITE_MS)
    },
    { deep: true },
  )

  function dropScratch(): void {
    if (scratchTimer) clearTimeout(scratchTimer)
    scratchTimer = null
    const toolKey = tool.value?.key
    const uid = userId.value
    if (toolKey && uid !== null) removeLocalDraft(uid, scratchKey(toolKey))
    scratchInputs.value = null
  }

  // ── Leaving ─────────────────────────────────────────────────────────

  const leaveGuard = useLeaveGuard({
    dirty: () => dirty.value,
    updates: true,
    confirm: () =>
      ask({
        group: 'tool-calculation',
        header: t('documents.leave.header'),
        message: t('documents.leave.message'),
        icon: 'mdi mdi-alert-outline',
        rejectProps: { label: t('common.cancel'), severity: 'secondary' },
        acceptProps: { label: t('documents.leave.accept'), severity: 'warn' },
      }),
  })

  /** Whether the tool shows changes, saved calculation or not; New and Load ask first then. */
  const hasUnsavedChanges = computed(() => {
    const s = ownState.value
    if (!s) return false
    if (current.value) return dirty.value
    return baseline.value !== null && !inputsEqual(s.inputs, baseline.value)
  })

  const differences = computed(() => {
    const calc = current.value
    const s = ownState.value
    if (!calc || !s || dirty.value) return []
    return resultDifferences(calc.results, s.results)
  })
  const drift = computed(() => differences.value.length > 0)

  const lifecycle = useControlledDocument<CalculationResponse, { inputs: Record<string, string> }>({
    document: calculation,
    current,
    opened: publicId,
    resource: LiveResource.CALCULATIONS,
    api: {
      get: getCalculation,
      lock: lockCalculation,
      unlock: unlockCalculation,
      release: releaseCalculation,
      markInvalid: markCalculationInvalid,
      revise: reviseCalculation,
      remove: deleteCalculation,
    },
    permissions: {
      write: Permission.WRITE_CALCULATIONS,
      manage: Permission.MANAGE_CALCULATIONS,
      release: Permission.RELEASE_CALCULATIONS,
    },
    // The tool keeps showing its inputs; only the record moves on.
    show: (saved) => {
      calculation.value = saved
    },
    apply: (loaded, editing) => {
      const before = calculation.value
      calculation.value = loaded
      // Someone else saved other inputs: the tool shows them, unless the user
      // is trying something out on screen.
      if (!editing && before && !dirty.value && JSON.stringify(before.inputs) !== JSON.stringify(loaded.inputs)) {
        remount()
      }
    },
    // Discarding puts the tool back on the saved inputs.
    revert: () => {
      if (dirty.value) remount()
    },
    draft: {
      name: 'calculation',
      value: () => (dirty.value && ownState.value ? { inputs: ownState.value.inputs } : null),
    },
    offered: {
      // A calculation is released only as saved and as it calculates now;
      // while it is edited, Release saves the screen first.
      release: ({ editing }) =>
        !!current.value && current.value.released_at == null && (editing || (!dirty.value && !drift.value)),
      revise: () => current.value?.released_at != null && current.value.is_latest && !dirty.value,
    },
    // The changes on screen are kept in this browser and offered back.
    onLost: () => remount(),
    // After inactivity the inputs stay on screen as figures being tried out.
    offerDraftAfterIdle: false,
    afterRevise: (created) => show(created),
    afterRemove: () => detach(),
  })
  const { draft, lock, run } = lifecycle

  const canCreate = computed(() => hasPermission(Permission.WRITE_CALCULATIONS))
  const editing = computed(() => !!current.value && lock.editing.value)
  /** Whether Save writes into the open calculation. */
  const canUpdate = computed(() => lifecycle.canChange.value && editing.value)
  // A saved calculation prints only as saved: unsaved edits or results that
  // differ from the snapshot would put numbers on paper the record does not
  // hold.
  const canPrint = computed(() => !!ownState.value && !dirty.value && !drift.value)

  function payload() {
    const s = ownState.value
    const def = tool.value
    if (!s || !def) throw new Error('No tool state to save.')
    return {
      inputs: s.inputs,
      results: s.results,
      input_version: def.inputVersion,
      engine_version: def.engineVersion,
    }
  }

  // The tool keeps running on what it already shows; only the route learns
  // which calculation that now is.
  async function show(saved: CalculationResponse): Promise<void> {
    calculation.value = saved
    if (publicId.value !== saved.public_id) {
      leaveGuard.allowNext()
      await router.replace(toolPath(activeTab.value, saved.public_id))
    }
  }

  async function saveNew(meta: CalculationMeta): Promise<CalculationResponse> {
    return run(async () => {
      const saved = await createCalculation({
        tool: tool.value?.key ?? '',
        title: meta.title,
        note: meta.note,
        ...ownerIds(meta.owner),
        product_device_id: meta.deviceId,
        ...payload(),
      })
      dropScratch()
      await show(saved)
      return saved
    })
  }

  /** Saves the current inputs into the open calculation, optionally with new metadata. */
  async function save(meta?: CalculationMeta): Promise<CalculationResponse> {
    const calc = current.value
    if (!calc) throw new Error('No saved calculation is open.')
    return run(async () => {
      const saved = await updateCalculation(calc.id, {
        title: meta?.title ?? calc.title,
        note: meta ? meta.note : calc.note,
        ...ownerIds(meta?.owner ?? ownerOf(calc)),
        product_device_id: meta ? meta.deviceId : calc.product_device_id,
        ...payload(),
      })
      calculation.value = saved
      return saved
    })
  }

  /** Whether a release saves the screen first: changed inputs, or results the tool now calculates differently. */
  const releaseSavesFirst = computed(() => dirty.value || drift.value)

  /** Releases the open calculation; while it is edited, unsaved inputs are saved first and the release ends editing. */
  async function release(): Promise<void> {
    if (releaseSavesFirst.value) await save()
    await lifecycle.release()
  }

  /** Leaves the saved calculation; the tool keeps its inputs as its scratch copy. */
  async function detach(): Promise<void> {
    calculation.value = null
    leaveGuard.allowNext()
    await router.replace(toolPath(activeTab.value, null))
  }

  /** Leaves the open calculation and starts the tool afresh with cleared inputs. */
  async function startNew(): Promise<void> {
    await detach()
    dropScratch()
    remount()
  }

  /** Opens another calculation of the tool; the caller has asked about unsaved changes. */
  async function open(publicIdToOpen: string): Promise<void> {
    leaveGuard.allowNext()
    await router.push(toolPath(activeTab.value, publicIdToOpen))
  }

  return {
    calculation: current,
    toolReady,
    initialInputs,
    mountKey,
    hasUnsavedChanges,
    resolving,
    loadFailed,
    busy: lifecycle.busy,
    dirty,
    drift,
    differences,
    released: lifecycle.released,
    editing,
    revisions,
    latestRevision,
    lock,
    lostBy: lifecycle.lostBy,
    idleEnded: lifecycle.idleEnded,
    draft,
    restoreDraft,
    offered: lifecycle.offered,
    missing: lifecycle.missing,
    canCreate,
    canUpdate,
    canEdit: lifecycle.canEdit,
    canTakeOver: lifecycle.canTakeOver,
    takeOverBlocked: lifecycle.takeOverBlocked,
    canRelease: lifecycle.canRelease,
    canMarkInvalid: lifecycle.canMarkInvalid,
    canRevise: lifecycle.canRevise,
    canDelete: lifecycle.canDelete,
    canPrint,
    saveNew,
    save,
    release,
    releaseSavesFirst,
    markInvalid: lifecycle.markInvalid,
    revise: lifecycle.revise,
    startEditing: lifecycle.startEditing,
    finishEditing: lifecycle.discard,
    detach,
    open,
    remove: lifecycle.remove,
    startNew,
  }
}

export type SavedCalculation = ReturnType<typeof useSavedCalculation>
