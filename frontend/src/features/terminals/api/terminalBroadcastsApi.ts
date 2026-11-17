import { webApi } from '@/core/api/webRequest'

import type {
  TerminalBroadcastAudienceRequest,
  TerminalBroadcastCreateRequest,
  TerminalBroadcastResponse,
} from '../types/terminalResponse'

/** The messages shown on terminals right now, newest first. */
export async function getActiveTerminalBroadcasts(): Promise<TerminalBroadcastResponse[]> {
  return webApi.get('/terminal-broadcasts/')
}

export async function sendTerminalBroadcast(
  body: TerminalBroadcastCreateRequest,
): Promise<TerminalBroadcastResponse> {
  return webApi.post('/terminal-broadcasts/', { body })
}

/** How many approved terminals an audience reaches now; an empty pick counts 0. */
export async function countTerminalBroadcastReach(
  body: TerminalBroadcastAudienceRequest,
): Promise<number> {
  const response = await webApi.post('/terminal-broadcasts/reach', { body })
  return response.count
}

/** Ends a message at once; ending one that already ended changes nothing. */
export async function endTerminalBroadcast(broadcastId: number): Promise<TerminalBroadcastResponse> {
  return webApi.post('/terminal-broadcasts/{broadcast_id}/end', {
    path: { broadcast_id: broadcastId },
  })
}
