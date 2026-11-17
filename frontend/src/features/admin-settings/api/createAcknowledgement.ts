import { webApi } from '@/core/api/webRequest'
import type { Acknowledgement, CreateAcknowledgementCommand } from '../types/acknowledgementTypes'

export async function createAcknowledgement(
  cmd: CreateAcknowledgementCommand,
): Promise<Acknowledgement> {
  return webApi.post('/admin/acknowledgements/', { body: cmd })
}
