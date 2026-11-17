import { webApi } from '@/core/api/webRequest'
import type { PageResponse } from '@/core/api/types'
import type {
  AgentCall,
  AgentCallParams,
  AgentConsentStatus,
  AgentCreatedRecord,
  AgentSettings,
  UpdateAgentSettingsCommand,
} from '../types/agentTypes'

export async function getAgentSettings(): Promise<AgentSettings> {
  return webApi.get('/admin/settings/agents')
}

export async function updateAgentSettings(cmd: UpdateAgentSettingsCommand): Promise<AgentSettings> {
  return webApi.put('/admin/settings/agents', { body: cmd })
}

/** The terms the consent dialog shows and whether the caller confirmed the current ones. */
export async function getMyAgentConsent(): Promise<AgentConsentStatus> {
  return webApi.get('/users/me/agent-consent')
}

/** Confirms the consent text of the given version, as the status returned it. */
export async function giveAgentConsent(consentVersion: number): Promise<AgentConsentStatus> {
  return webApi.put('/users/me/agent-consent', { body: { consent_version: consentVersion } })
}

/** Withdraws the consent and revokes every agent token of the caller. */
export async function withdrawAgentConsent(): Promise<AgentConsentStatus> {
  return webApi.delete('/users/me/agent-consent')
}

/** The agent call log: the caller's own calls, or every call for read:settings. */
export async function getAgentCalls(params: AgentCallParams): Promise<PageResponse<AgentCall>> {
  return webApi.get('/agent-calls/', { query: params })
}

/** Which of these records, each `<kind>:<public id>`, an agent created. At most 200 at once. */
export async function findAgentCreatedRecords(refs: string[]): Promise<AgentCreatedRecord[]> {
  return webApi.post('/agent-calls/created-records', { body: { refs } })
}
