import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { getLot } from '../../api/getLot'
import { getLotChangelog } from '../api/getLotChangelog'
import { getLotCompletions } from '../api/getLotCompletions'
import { getLotEvents } from '../api/getLotEvents'
import { addLotStep } from '../api/addLotStep'
import { updateLotStep } from '../api/updateLotStep'
import { deleteLotStep } from '../api/deleteLotStep'
import { reorderLotSteps } from '../api/reorderLotSteps'
import { regroupLotPositions } from '../api/regroupLotPositions'
import { appendLotPosition } from '../api/appendLotPosition'
import { replaceLotStructure } from '../api/replaceLotStructure'
import { assignExternalPosition } from '../api/assignExternalPosition'
import { unassignExternalPosition } from '../api/unassignExternalPosition'
import { assignInternalPosition } from '../api/assignInternalPosition'
import { cancelLot } from '../../api/cancelLot'
import { reverseProductionOrderCompletion } from '../../api/reverseProductionOrderCompletion'
import { completeLot } from '../../api/completeLot'
import { holdLot } from '../api/holdLot'
import { resumeLot } from '../api/resumeLot'
import { recordLotPositionProvision } from '../api/recordLotPositionProvision'
import { getLotPositionProvisions } from '../api/getLotPositionProvisions'

import type {
  AddLotStepRequest,
  AppendLotPositionRequest,
  AssignExternalPositionRequest,
  AssignInternalPositionRequest,
  RecordLotPositionProvisionRequest,
  ReplaceLotStructureRequest,
  UpdateLotStepRequest,
} from '../../types/productionLotsRequest'
import type {
  LotEventResponse,
  LotPositionCompletionResponse,
  LotPositionProvisionResponse,
  LotResponse,
} from '../../types/productionLotsResponse'

export const useProductionLotDetailStore = defineStore('productionLotDetail', () => {
  // Sequenced so that switching lots quickly (e.g. paging through a list
  // with this panel open) can't let a slower fetch for a previous lot land
  // after a faster fetch for the current one and overwrite it.
  const { loading, error, run } = useSequencedFetch(getLot)
  const lot = ref<LotResponse | null>(null)
  const mutating = ref(false)
  const changelog = ref<string[]>([])
  const completions = ref<LotPositionCompletionResponse[]>([])
  const events = ref<LotEventResponse[]>([])

  async function fetch(lotId: number): Promise<void> {
    const result = await run(lotId)
    if (result) lot.value = result
  }

  async function fetchChangelog(lotId: number): Promise<void> {
    changelog.value = await getLotChangelog(lotId)
  }

  async function fetchCompletions(lotId: number): Promise<void> {
    completions.value = await getLotCompletions(lotId)
  }

  async function fetchEvents(lotId: number): Promise<void> {
    events.value = await getLotEvents(lotId)
  }

  async function refetch(): Promise<void> {
    if (lot.value) await fetch(lot.value.id)
  }

  function clear(): void {
    lot.value = null
    changelog.value = []
    completions.value = []
    events.value = []
  }

  async function withMutation<T>(action: () => Promise<T>): Promise<T> {
    mutating.value = true
    try {
      const result = await action()
      await refetch()
      return result
    } finally {
      mutating.value = false
    }
  }

  async function addStep(lotId: number, payload: AddLotStepRequest): Promise<void> {
    await withMutation(() => addLotStep(lotId, payload))
  }

  async function updateStep(
    lotId: number,
    stepId: number,
    payload: UpdateLotStepRequest,
  ): Promise<void> {
    await withMutation(() => updateLotStep(lotId, stepId, payload))
  }

  async function removeStep(lotId: number, stepId: number): Promise<void> {
    await withMutation(() => deleteLotStep(lotId, stepId))
  }

  async function reorderSteps(lotId: number, orderedStepIds: number[]): Promise<void> {
    await withMutation(() => reorderLotSteps(lotId, orderedStepIds))
  }

  async function regroupPositions(lotId: number, groups: number[][]): Promise<void> {
    await withMutation(() => regroupLotPositions(lotId, groups))
  }

  async function appendPosition(lotId: number, payload: AppendLotPositionRequest): Promise<void> {
    await withMutation(() => appendLotPosition(lotId, payload))
  }

  async function saveStructure(lotId: number, payload: ReplaceLotStructureRequest): Promise<void> {
    await withMutation(() => replaceLotStructure(lotId, payload))
  }

  async function assignPosition(
    lotId: number,
    positionId: number,
    payload: AssignExternalPositionRequest,
  ): Promise<void> {
    await withMutation(() => assignExternalPosition(lotId, positionId, payload))
  }

  async function unassignPosition(lotId: number, positionId: number): Promise<void> {
    await withMutation(() => unassignExternalPosition(lotId, positionId))
  }

  async function assignInternal(
    lotId: number,
    positionId: number,
    payload: AssignInternalPositionRequest,
  ): Promise<void> {
    await withMutation(() => assignInternalPosition(lotId, positionId, payload))
  }

  // An irreversible action carries the lot's edit version as the caller
  // showed it, so a concurrent change answers 409.
  async function cancel(lotId: number, editVersion: number, reason?: string | null): Promise<void> {
    await withMutation(() => cancelLot(lotId, { reason, expected_edit_version: editVersion }))
  }

  async function complete(
    lotId: number,
    editVersion: number,
    reason?: string | null,
  ): Promise<void> {
    await withMutation(() => completeLot(lotId, { reason, expected_edit_version: editVersion }))
  }

  async function hold(lotId: number, reason: string): Promise<void> {
    await withMutation(() => holdLot(lotId, { reason }))
  }

  async function resume(lotId: number): Promise<void> {
    await withMutation(() => resumeLot(lotId))
  }

  async function recordProvision(
    lotId: number,
    positionId: number,
    payload: RecordLotPositionProvisionRequest,
  ): Promise<void> {
    await withMutation(() => recordLotPositionProvision(lotId, positionId, payload))
  }

  // The reversal changes the lot's record as well as the order, so the
  // completions and events are read again with the lot.
  async function reverseCompletion(
    productionOrderId: number,
    completionId: number,
    reason: string,
  ): Promise<void> {
    await withMutation(() =>
      reverseProductionOrderCompletion(productionOrderId, completionId, { reason }),
    )
    if (lot.value) {
      await Promise.all([fetchCompletions(lot.value.id), fetchEvents(lot.value.id)])
    }
  }

  async function fetchProvisions(
    lotId: number,
    positionId: number,
  ): Promise<LotPositionProvisionResponse[]> {
    return getLotPositionProvisions(lotId, positionId)
  }

  return {
    lot,
    loading,
    error,
    mutating,
    changelog,
    completions,
    events,
    fetch,
    fetchChangelog,
    fetchCompletions,
    fetchEvents,
    refetch,
    clear,
    addStep,
    updateStep,
    removeStep,
    reorderSteps,
    regroupPositions,
    appendPosition,
    saveStructure,
    assignPosition,
    unassignPosition,
    assignInternal,
    cancel,
    complete,
    reverseCompletion,
    hold,
    resume,
    recordProvision,
    fetchProvisions,
  }
})
