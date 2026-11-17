import { computed, ref, watch, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'
import { useProductionQueueStore } from '../../stores/productionQueueStore'
import { parseAssignTargetKey } from '../utils/lotStepAssignOptions'
import { MADE_ITEM_ORDER_UNIT } from '../../utils/madeItemOrderUnit'
import { extractApiError } from '@/core/utils/errors'

import type { ReplaceLotStructureStepRequest } from '../../types/productionLotsRequest'
import type {
  FabricationLotStep,
  InspectionLotStep,
  LotPositionResponse,
  LotResponse,
  LotStepResponse,
} from '../../types/productionLotsResponse'
import { bySequence, sortedBySequence } from '../../utils/sequence'

// A local, unsaved copy of a lot's step and position structure. save()
// writes it through one transactional request, so a rejected edit never
// leaves the lot half-changed. New steps carry a negative placeholder id
// until saved.
export interface LotDraftPosition {
  id: number
  steps: LotStepResponse[]
}

// eslint-disable-next-line no-restricted-syntax -- a patch of the local step draft, where a method id is never cleared
export type LotStepPatch = Partial<{
  fabrication_method_id: number
  inspection_method_id: number
  note: string | null
  estimated_setup_minutes: number | null
  estimated_minutes_per_piece: number | null
}>

export type AppendedStep =
  | { role: 'fabrication'; fabrication_method_id: number }
  | { role: 'inspection'; inspection_method_id: number }

// draft position id → AssignTargetKey ('pool:9' | 'machine:1' | 'manual' | 'order:42')
export type PendingAssignments = Record<number, string>
// production order id → 'pool:<id>' | 'machine:<id>' | null (= clear the target)
export type PendingReassignments = Record<number, string | null>

export function useLotStructureDraft(lot: Ref<LotResponse | null>) {
  const detailStore = useProductionLotDetailStore()
  const queueStore = useProductionQueueStore()
  const { t } = useI18n()
  const toast = useAppToast()

  const draft = ref<LotDraftPosition[]>([])
  const saving = ref(false)
  let nextTempId = -1

  // Staged machine and order picks, written only by save(). Separate maps,
  // because an assignment addresses a position, which may still have a
  // placeholder id, while a reassignment addresses an existing order.
  const pendingAssignmentsRaw = ref<PendingAssignments>({})
  const pendingReassignmentsRaw = ref<PendingReassignments>({})

  function buildDraft(): LotDraftPosition[] {
    return [...(lot.value?.positions ?? [])]
      .sort(bySequence)
      .map((position) => ({
        id: position.id,
        steps: [...(position.steps ?? [])]
          .sort(bySequence)
          .map((s) => ({ ...s })),
      }))
  }

  // Rebuilds only the step draft, never the pick maps, because save()
  // itself triggers refetches while it is still applying them.
  function rebuildDraft(): void {
    nextTempId = -1
    draft.value = buildDraft()
  }

  function reset(): void {
    rebuildDraft()
    pendingAssignmentsRaw.value = {}
    pendingReassignmentsRaw.value = {}
  }

  // Rebuilt on every load, so the draft starts from what is stored. Stale
  // picks are filtered for display and dropped by save().
  watch(lot, rebuildDraft, { immediate: true })

  // Flattened views for the child components, which speak steps +
  // positions. Sequences are recomputed from the draft order so the table
  // and the grouping chain read the staged structure, not the stored one.
  const draftSteps = computed<LotStepResponse[]>(() =>
    draft.value.flatMap((position, positionIndex) =>
      position.steps.map((step, stepIndex) => ({
        ...step,
        position_id: position.id,
        sequence: positionIndex * 1000 + stepIndex,
      })),
    ),
  )

  const draftPositions = computed<LotPositionResponse[]>(() => {
    const stored = new Map((lot.value?.positions ?? []).map((p) => [p.id, p]))
    return draft.value.map((position, index) => ({
      // Built from the draft only; a fresh `new Date()` would make this
      // computed change on every read.
      ...(stored.get(position.id) ??
        ({
          id: position.id,
          public_id: '',
          created: position.steps[0]?.created ?? '',
          changed: null,
          changed_by: null,
          changed_by_id: null,
          kind: 'unassigned',
          status: 'pending',
          quantity: lot.value?.quantity ?? 0,
          quantity_completed: 0,
          quantity_remaining: lot.value?.quantity ?? 0,
          note: null,
          creator_id: 0,
          lot_id: lot.value?.id ?? 0,
          order_item_id: null,
          order_id: null,
          order_number: '',
          supplier_name: '',
          order_item_status: '',
          order_item_closed_short: false,
          earlier_order_lines: [],
          expected_delivery_date: null,
          planned_delivery_date: null,
          planned_pickup_date: null,
          actions: [],
          production_orders: [],
        } as Omit<LotPositionResponse, 'sequence' | 'steps'>)),
      sequence: index + 1,
      steps: draftSteps.value.filter((s) => s.position_id === position.id),
    }))
  })

  // Exposed through the draft's current shape, since raw entries can point
  // at regrouped positions or canceled orders.
  const pendingAssignments = computed<PendingAssignments>(() => {
    const result: PendingAssignments = {}
    for (const [key, value] of Object.entries(pendingAssignmentsRaw.value)) {
      const positionId = Number(key)
      const position = draftPositions.value.find((p) => p.id === positionId)
      if (position && position.kind === 'unassigned') result[positionId] = value
    }
    return result
  })

  const pendingReassignments = computed<PendingReassignments>(() => {
    const liveOrderIds = new Set(
      draftPositions.value.flatMap((p) => (p.production_orders ?? []).map((o) => o.id)),
    )
    const result: PendingReassignments = {}
    for (const [key, value] of Object.entries(pendingReassignmentsRaw.value)) {
      const orderId = Number(key)
      if (liveOrderIds.has(orderId)) result[orderId] = value
    }
    return result
  })

  const isDirty = computed(
    () =>
      JSON.stringify(draft.value) !== JSON.stringify(buildDraft()) ||
      Object.keys(pendingAssignments.value).length > 0 ||
      Object.keys(pendingReassignments.value).length > 0,
  )

  // ── Staged edits ───────────────────────────────────────────────────

  function editStep(stepId: number, patch: LotStepPatch): void {
    for (const position of draft.value) {
      const step = position.steps.find((s) => s.id === stepId)
      if (!step) continue
      // Only real changes, or an echoing input would re-render in a loop.
      const changed = Object.entries(patch).filter(
        ([key, value]) => step[key as keyof typeof step] !== value,
      )
      if (changed.length > 0) Object.assign(step, Object.fromEntries(changed))
    }
  }

  function removeStep(stepId: number): void {
    for (const position of draft.value) {
      position.steps = position.steps.filter((s) => s.id !== stepId)
    }
    // A position with no steps left ceases to exist, same as the
    // backend's own delete cascade.
    draft.value = draft.value.filter((position) => position.steps.length > 0)
  }

  // Placeholder fields shared by both step kinds.
  function stagedStepBase(id: number) {
    return {
      id,
      public_id: `staged-${id}`,
      created: new Date().toISOString(),
      note: null,
      estimated_setup_minutes: null,
      estimated_minutes_per_piece: null,
      time_budget_per_piece: null,
      sequence: 0,
      creator_id: 0,
      lot_id: lot.value?.id ?? 0,
      position_id: id,
      source_process_id: null,
      fabrication_method_name: {},
      fabrication_method_requires_machine: false,
      fabrication_method_required_external: false,
      fabrication_method_default_supplier_id: null,
    }
  }

  function buildFabricationStep(id: number, fabricationMethodId: number): FabricationLotStep {
    return {
      ...stagedStepBase(id),
      role: 'fabrication',
      fabrication_method_id: fabricationMethodId,
      inspection_method_id: null,
      inspection_method_name: null,
      inspection_method_requires_evidence: null,
    }
  }

  function buildInspectionStep(id: number, inspectionMethodId: number): InspectionLotStep {
    return {
      ...stagedStepBase(id),
      role: 'inspection',
      fabrication_method_requires_machine: false,
      fabrication_method_id: null,
      inspection_method_id: inspectionMethodId,
      inspection_method_name: {},
      inspection_method_requires_evidence: false,
    }
  }

  function appendStep(step: AppendedStep): void {
    const id = nextTempId--
    const newStep: LotStepResponse =
      step.role === 'fabrication'
        ? buildFabricationStep(id, step.fabrication_method_id)
        : buildInspectionStep(id, step.inspection_method_id)
    draft.value = [...draft.value, { id, steps: [newStep] }]
  }

  function reorderPositions(orderedPositionIds: number[]): void {
    const byId = new Map(draft.value.map((position) => [position.id, position]))
    draft.value = orderedPositionIds
      .map((id) => byId.get(id))
      .filter((position): position is LotDraftPosition => position !== undefined)
  }

  function regroup(groups: number[][]): void {
    const stepsById = new Map(draft.value.flatMap((p) => p.steps).map((s) => [s.id, s]))
    const previous = draft.value
    draft.value = groups.map((group) => {
      const steps = group
        .map((stepId) => stepsById.get(stepId))
        .filter((step): step is LotStepResponse => step !== undefined)
      // Keep the position whose step set is unchanged, so the backend preserves
      // its assignment and orders.
      const unchanged = previous.find(
        (position) =>
          position.steps.length === steps.length &&
          position.steps.every((s, index) => s.id === steps[index]?.id),
      )
      return { id: unchanged?.id ?? nextTempId--, steps }
    })
  }

  // ── Staged assignment ────────────────────────────────────────────────
  // Picks are only recorded here and sent by save().

  function assignPosition(positionId: number, key: string): void {
    pendingAssignmentsRaw.value = { ...pendingAssignmentsRaw.value, [positionId]: key }
  }

  function clearAssignment(positionId: number): void {
    const next = { ...pendingAssignmentsRaw.value }
    delete next[positionId]
    pendingAssignmentsRaw.value = next
  }

  function reassignOrder(orderId: number, key: string | null): void {
    pendingReassignmentsRaw.value = { ...pendingReassignmentsRaw.value, [orderId]: key }
  }

  function clearReassignment(orderId: number): void {
    const next = { ...pendingReassignmentsRaw.value }
    delete next[orderId]
    pendingReassignmentsRaw.value = next
  }

  // ── Save ───────────────────────────────────────────────────────────

  function toPayloadStep(step: LotStepResponse): ReplaceLotStructureStepRequest {
    return {
      id: step.id > 0 ? step.id : null,
      role: step.role,
      fabrication_method_id: step.fabrication_method_id,
      inspection_method_id: step.inspection_method_id,
      note: step.note,
      estimated_setup_minutes: step.estimated_setup_minutes,
      estimated_minutes_per_piece: step.estimated_minutes_per_piece,
    }
  }

  // A failed pick is not fatal: the structure is already saved, so the
  // remaining picks stay staged and the planner can save again.
  async function failSave(summary: string, e: unknown): Promise<false> {
    toast.error(summary, extractApiError(e) ?? undefined)
    await queueStore.fetchOrders()
    return false
  }

  async function save(lotId: number): Promise<boolean> {
    saving.value = true
    try {
      // Snapshot before saveStructure() below can change what buildDraft()
      // reflects (it reads off `lot`, which a structure save refetches).
      const draftIds = draft.value.map((position) => position.id)
      const structureDirty = JSON.stringify(draft.value) !== JSON.stringify(buildDraft())

      if (structureDirty) {
        // A failure here aborts save() before any pick is applied.
        await detailStore.saveStructure(lotId, {
          positions: draft.value.map((position) => ({ steps: position.steps.map(toPayloadStep) })),
        })
      }

      // Group i is saved with sequence i + 1, so draft and saved positions
      // match by index; this is how placeholder ids find their real ones.
      const saved = sortedBySequence(lot.value?.positions)
      if (saved.length !== draftIds.length) {
        throw new Error('lot structure changed underneath the draft')
      }
      const rekeyedAssignments: PendingAssignments = {}
      draftIds.forEach((draftId, index) => {
        const pending = pendingAssignmentsRaw.value[draftId]
        if (pending !== undefined) rekeyedAssignments[saved[index]!.id] = pending
      })
      pendingAssignmentsRaw.value = rekeyedAssignments

      // Assignments first, with the same payload as the unstaged path.
      for (const position of saved) {
        const key = pendingAssignmentsRaw.value[position.id]
        if (key === undefined) continue
        const parsed = parseAssignTargetKey(key)
        // 'order:new' is never staged; defensive only.
        if (!parsed || parsed.kind === 'create') continue

        try {
          if (parsed.kind === 'order') {
            await detailStore.assignPosition(lotId, position.id, {
              order_id: parsed.id,
              unit: MADE_ITEM_ORDER_UNIT,
              items_per_unit: 1,
              price: null,
              expected_delivery_date: null,
              expected_pickup_date: null,
              quantity: position.quantity_remaining,
            })
          } else {
            const orderInput =
              parsed.kind === 'pool'
                ? { machine_pool_id: parsed.id, quantity: position.quantity_remaining }
                : parsed.kind === 'machine'
                  ? { machine_id: parsed.id, quantity: position.quantity_remaining }
                  : { machine_id: null, quantity: position.quantity_remaining }
            await detailStore.assignInternal(lotId, position.id, { orders: [orderInput] })
          }
          clearAssignment(position.id)
        } catch (e) {
          return await failSave(
            t('production.lots.editSteps.assignSaveError', { sequence: position.sequence }),
            e,
          )
        }
      }

      // Then reassignments: each one moves an already-existing order to a
      // different machine/pool, or (a null key) clears its target.
      let anyReassigned = false
      for (const [orderIdKey, key] of Object.entries(pendingReassignmentsRaw.value)) {
        const orderId = Number(orderIdKey)
        try {
          const target =
            key === null
              ? null
              : key.startsWith('pool:')
                ? { machinePoolId: Number(key.slice('pool:'.length)) }
                : Number(key.slice('machine:'.length))
          await queueStore.reassignMachine(orderId, target)
          anyReassigned = true
          clearReassignment(orderId)
        } catch (e) {
          const orderNumber =
            queueStore.orders.find((o) => o.id === orderId)?.production_order_number ?? orderId
          return await failSave(
            t('production.lots.editSteps.reassignSaveError', { number: orderNumber }),
            e,
          )
        }
      }
      // The lot's own copy of the orders needs a refetch too.
      if (anyReassigned) await detailStore.refetch()

      await queueStore.fetchOrders()
      return true
    } finally {
      saving.value = false
    }
  }

  return {
    draftSteps,
    draftPositions,
    isDirty,
    saving,
    pendingAssignments,
    pendingReassignments,
    editStep,
    removeStep,
    appendStep,
    reorderPositions,
    regroup,
    assignPosition,
    clearAssignment,
    reassignOrder,
    clearReassignment,
    save,
    reset,
  }
}
