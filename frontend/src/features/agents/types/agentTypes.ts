import type { QueryOf } from '@/core/api/webRequest'
import type { Schemas } from '@/core/api/generated'

export type AgentSettings = Schemas['AdminAgentSettingsResponse']

export type UpdateAgentSettingsCommand = Schemas['UpdateAgentSettingsRequest']

export type AgentConsentStatus = Schemas['AgentConsentStatusResult']

export type AgentCall = Schemas['AgentCallResult']

export type AgentCallOutcome = Schemas['AgentCallOutcome']

export type AgentCallParams = QueryOf<'/agent-calls/'>

export type AgentCreatedRecord = Schemas['AgentCreatedRecordResult']

/** The kinds of record an agent drafts, as the call log names them. */
export type AgentDraftKind = 'order' | 'quote_request' | 'lot'
