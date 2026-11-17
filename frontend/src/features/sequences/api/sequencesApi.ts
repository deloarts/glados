import { webApi } from '@/core/api/webRequest'
import type { PageResponse } from '@/core/api/types'
import type {
  SequenceCreateRequest,
  SequenceListParams,
  SequenceResponse,
  SequenceSummaryResponse,
  SequenceUpdateRequest,
} from '../types/sequence'

type Raw = Omit<SequenceResponse, 'changes'> & { changes?: string[] }

function withChanges(sequence: Raw): SequenceResponse {
  return { ...sequence, changes: sequence.changes ?? [] }
}

export async function getSequences(params: SequenceListParams): Promise<PageResponse<SequenceSummaryResponse>> {
  return webApi.get('/sequences', { query: params })
}

export async function getSequence(id: number): Promise<SequenceResponse> {
  return withChanges(await webApi.get('/sequences/{sequence_id}', { path: { sequence_id: id } }))
}

export async function getSequenceRevisions(id: number): Promise<SequenceSummaryResponse[]> {
  return webApi.get('/sequences/{sequence_id}/revisions', { path: { sequence_id: id } })
}

export async function createSequence(body: SequenceCreateRequest): Promise<SequenceResponse> {
  return withChanges(await webApi.post('/sequences', { body }))
}

export async function updateSequence(id: number, body: SequenceUpdateRequest): Promise<SequenceResponse> {
  return withChanges(await webApi.put('/sequences/{sequence_id}', { path: { sequence_id: id }, body }))
}

/** Takes the edit lock, or renews the one the caller holds; `takeOver` takes it from another editor. */
export async function lockSequence(id: number, takeOver = false): Promise<SequenceResponse> {
  return withChanges(
    await webApi.post('/sequences/{sequence_id}/lock', { path: { sequence_id: id }, body: { take_over: takeOver } }),
  )
}

/** Ends the edit lock the caller holds; `force` ends anyone's, which needs manage:sequences. */
export async function unlockSequence(id: number, force = false): Promise<SequenceResponse> {
  return withChanges(
    await webApi.delete('/sequences/{sequence_id}/lock', { path: { sequence_id: id }, query: { force } }),
  )
}

export async function releaseSequence(id: number): Promise<SequenceResponse> {
  return withChanges(await webApi.post('/sequences/{sequence_id}/release', { path: { sequence_id: id } }))
}

export async function reviseSequence(id: number, reason: string): Promise<SequenceResponse> {
  return withChanges(
    await webApi.post('/sequences/{sequence_id}/revise', { path: { sequence_id: id }, body: { reason } }),
  )
}

export async function markSequenceInvalid(id: number, reason: string): Promise<SequenceResponse> {
  return withChanges(
    await webApi.post('/sequences/{sequence_id}/mark-invalid', { path: { sequence_id: id }, body: { reason } }),
  )
}

export async function deleteSequence(id: number): Promise<void> {
  await webApi.delete('/sequences/{sequence_id}', { path: { sequence_id: id } })
}
