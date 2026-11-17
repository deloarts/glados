import { computed, ref, watch } from 'vue'
import type { Ref } from 'vue'

import { Permission } from '@/core/auth/permissions'
import { LiveResource } from '@/core/realtime/resources'
import { getProductDevices } from '@/features/product-devices'
import type { ProductDevice } from '@/features/product-devices'
import { useControlledDocument } from '@/shared/documents'
import type { DocumentAction } from '@/shared/documents'
import { getSequenceProduct } from '../api/productApi'
import type { SequenceProduct } from '../api/productApi'
import { getProductVariants } from '../api/productVariantsApi'
import {
  deleteSequence,
  getSequence,
  getSequenceRevisions,
  lockSequence,
  markSequenceInvalid,
  releaseSequence,
  reviseSequence,
  unlockSequence,
  updateSequence,
} from '../api/sequencesApi'
import type { ProductVariant, SequenceResponse, SequenceStep, SequenceSummaryResponse } from '../types/sequence'
import { normalizeSteps, sameSteps } from '../utils/steps'

/** The unsaved changes of a sequence as this browser keeps them. */
interface SequenceDraft {
  name: string
  steps: SequenceStep[]
}

/** Why a sequence cannot be released right now, in the order they are shown. */
export type SequenceReleaseBlocker = 'empty'

/** The steps of a sequence the page offers as buttons. */
export type SequenceAction = DocumentAction

/**
 * One sequence as its page edits it: the saved record, the name and steps
 * on screen, its product with the devices and variants the steps refer
 * to, and what the current user may do with it.
 *
 * A draft is changed only while the user holds its edit lock: Edit takes
 * it, Save keeps it, Discard ends it. Changes by others arrive through the
 * live stream. Unsaved changes are kept in this browser while they exist
 * and offered again when editing ended without them being saved.
 */
export function useSequenceDocument(sequenceId: Ref<number>) {
  const sequence = ref<SequenceResponse | null>(null)
  const revisions = ref<SequenceSummaryResponse[]>([])
  const product = ref<SequenceProduct | null>(null)
  const devices = ref<ProductDevice[]>([])
  const variants = ref<ProductVariant[]>([])
  const loading = ref(false)
  const loadFailed = ref(false)

  const name = ref('')
  const steps = ref<SequenceStep[]>([])

  function show(loaded: SequenceResponse): void {
    sequence.value = loaded
    name.value = loaded.name
    steps.value = normalizeSteps(loaded.steps)
  }

  // Archived devices and variants stay listed, so a step that names one
  // still shows its name.
  async function loadProduct(productId: number): Promise<void> {
    const [loadedDevices, loadedVariants] = await Promise.all([
      getProductDevices(productId, true),
      getProductVariants(productId, true),
    ])
    devices.value = loadedDevices
    variants.value = loadedVariants
  }

  // The product only decides the rights on its devices, so the page does
  // not wait for it, and without it the devices open read-only.
  function loadRights(productId: number): void {
    getSequenceProduct(productId)
      .then((loaded) => (product.value = loaded))
      .catch(() => (product.value = null))
  }

  /** Puts a device saved in its dialog in place of the one shown. */
  function replaceDevice(saved: ProductDevice): void {
    devices.value = devices.value.map((device) => (device.id === saved.id ? saved : device))
  }

  async function load(): Promise<void> {
    const id = sequenceId.value
    loading.value = true
    loadFailed.value = false
    try {
      const loaded = await getSequence(id)
      if (sequenceId.value !== id) return
      show(loaded)
      draft.check()
      loadRights(loaded.product_id)
      const [loadedRevisions] = await Promise.all([getSequenceRevisions(id), loadProduct(loaded.product_id)])
      revisions.value = loadedRevisions
    } catch {
      if (sequenceId.value !== id) return
      sequence.value = null
      loadFailed.value = true
    } finally {
      if (sequenceId.value === id) loading.value = false
    }
  }

  watch(
    sequenceId,
    (id) => {
      // Leaving the route fires this before unmount, when the id is NaN.
      if (Number.isInteger(id)) void load()
    },
    { immediate: true },
  )

  const dirty = computed(() => {
    const saved = sequence.value
    if (!saved || saved.read_only) return false
    return saved.name !== name.value.trim() || !sameSteps(saved.steps, steps.value)
  })

  const lifecycle = useControlledDocument<SequenceResponse, SequenceDraft, SequenceReleaseBlocker>({
    document: sequence,
    opened: sequenceId,
    resource: LiveResource.SEQUENCES,
    api: {
      get: getSequence,
      lock: lockSequence,
      unlock: unlockSequence,
      release: releaseSequence,
      markInvalid: markSequenceInvalid,
      revise: reviseSequence,
      remove: deleteSequence,
    },
    permissions: {
      write: Permission.WRITE_SEQUENCES,
      manage: Permission.MANAGE_SEQUENCES,
      release: Permission.RELEASE_SEQUENCES,
    },
    // While editing only the record's lock and release fields move on; the
    // steps on screen are the user's own.
    show,
    draft: {
      name: 'sequence',
      value: () => (dirty.value ? { name: name.value, steps: steps.value } : null),
      restore: (value) => {
        name.value = value.name
        steps.value = normalizeSteps(value.steps)
      },
    },
    releaseBlockers: () => {
      // The steps on screen count, since a release saves them first.
      const blockers: SequenceReleaseBlocker[] = []
      if (steps.value.length === 0) blockers.push('empty')
      return blockers
    },
    afterRelease: async (released) => {
      revisions.value = await getSequenceRevisions(released.id)
    },
  })
  const { draft, run } = lifecycle

  async function save(): Promise<void> {
    const current = sequence.value
    if (!current) return
    await run(async () => {
      show(await updateSequence(current.id, { name: name.value.trim(), steps: steps.value }))
    })
  }

  /** Releases the steps on screen: unsaved changes are saved first, and the release ends editing. */
  async function release(): Promise<void> {
    if (dirty.value) await save()
    await lifecycle.release()
  }

  return {
    sequence,
    revisions,
    product,
    devices,
    replaceDevice,
    variants,
    name,
    steps,
    loading,
    loadFailed,
    busy: lifecycle.busy,
    dirty,
    released: lifecycle.released,
    canUpdate: lifecycle.canChange,
    canEdit: lifecycle.canEdit,
    editable: lifecycle.editable,
    canTakeOver: lifecycle.canTakeOver,
    takeOverBlocked: lifecycle.takeOverBlocked,
    offered: lifecycle.offered,
    missing: lifecycle.missing,
    canRelease: lifecycle.canRelease,
    releaseBlockers: lifecycle.releaseBlockers,
    canMarkInvalid: lifecycle.canMarkInvalid,
    canRevise: lifecycle.canRevise,
    canDelete: lifecycle.canDelete,
    load,
    save,
    release,
    markInvalid: lifecycle.markInvalid,
    startEditing: lifecycle.startEditing,
    discard: lifecycle.discard,
    restoreDraft: lifecycle.restoreDraft,
    revise: lifecycle.revise,
    remove: lifecycle.remove,
    lock: lifecycle.lock,
    lostBy: lifecycle.lostBy,
    idleEnded: lifecycle.idleEnded,
    draft,
    draftBlocked: lifecycle.draftBlocked,
  }
}

export type SequenceDocument = ReturnType<typeof useSequenceDocument>
