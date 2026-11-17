import { webApi } from '@/core/api/webRequest'
import type { Acknowledgement } from '../types/acknowledgementTypes'

/** Newest first, per the contract: the backend does the ordering. */
export async function getAcknowledgements(): Promise<Acknowledgement[]> {
  return webApi.get('/admin/acknowledgements/')
}
