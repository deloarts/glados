import { webApi } from '@/core/api/webRequest'

import type {
  TerminalApproveRequest,
  TerminalBulkActionResponse,
  TerminalDisplayOverrideRequest,
  TerminalResponse,
  TerminalScreenOption,
  TerminalUpdateRequest,
} from '../types/terminalResponse'

/** Every terminal; pending ones whose pairing code expired are left out by the server. */
export async function getTerminals(): Promise<TerminalResponse[]> {
  return webApi.get('/terminals/')
}

/** Approves a pending terminal. The server answers 422 when the typed code does not match. */
export async function approveTerminal(
  terminalId: number,
  body: TerminalApproveRequest,
): Promise<TerminalResponse> {
  return webApi.post('/terminals/{terminal_id}/approve', {
    path: { terminal_id: terminalId },
    body,
  })
}

/**
 * Renames, places or reassigns a terminal; an explicit null screen unassigns
 * it and an explicit null location clears it.
 */
export async function updateTerminal(
  terminalId: number,
  body: TerminalUpdateRequest,
): Promise<TerminalResponse> {
  return webApi.patch('/terminals/{terminal_id}', { path: { terminal_id: terminalId }, body })
}

export async function revokeTerminal(terminalId: number): Promise<TerminalResponse> {
  return webApi.post('/terminals/{terminal_id}/revoke', { path: { terminal_id: terminalId } })
}

export async function reloadTerminal(terminalId: number): Promise<TerminalResponse> {
  return webApi.post('/terminals/{terminal_id}/reload', { path: { terminal_id: terminalId } })
}

export async function identifyTerminal(terminalId: number): Promise<TerminalResponse> {
  return webApi.post('/terminals/{terminal_id}/identify', { path: { terminal_id: terminalId } })
}

export async function deleteTerminal(terminalId: number): Promise<void> {
  await webApi.delete('/terminals/{terminal_id}', { path: { terminal_id: terminalId } })
}

/** The screens a terminal can show: every infoscreen that is not archived. */
export async function getScreenOptions(): Promise<TerminalScreenOption[]> {
  return webApi.get('/infoscreens/', { query: { include_archived: false } })
}

/**
 * Switches a display off or on by hand. Without `until` the override ends at
 * the next change of the screen's schedule; the server answers 422 when there
 * is none.
 */
export async function setDisplayOverride(
  terminalId: number,
  body: TerminalDisplayOverrideRequest,
): Promise<TerminalResponse> {
  return webApi.post('/terminals/{terminal_id}/display-override', {
    path: { terminal_id: terminalId },
    body,
  })
}

/** Hands the display back to its screen's schedule. */
export async function clearDisplayOverride(terminalId: number): Promise<TerminalResponse> {
  return webApi.delete('/terminals/{terminal_id}/display-override', {
    path: { terminal_id: terminalId },
  })
}

/** The actions that run on many terminals in one request. */
export type TerminalBulkAction = 'reload' | 'identify' | 'revoke' | 'delete'

/**
 * Runs an action on every approved terminal, or for delete on every terminal
 * including waiting and revoked ones, and answers how many it touched.
 */
export async function runBulkTerminalAction(action: TerminalBulkAction): Promise<number> {
  let response: TerminalBulkActionResponse
  switch (action) {
    case 'reload':
      response = await webApi.post('/terminals/all/reload')
      break
    case 'identify':
      response = await webApi.post('/terminals/all/identify')
      break
    case 'revoke':
      response = await webApi.post('/terminals/all/revoke')
      break
    case 'delete':
      response = await webApi.post('/terminals/all/delete')
      break
  }
  return response.count
}
