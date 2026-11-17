// Public barrel for the agents feature. Other features import through here
// (enforced by the no-restricted-imports rule in eslint.config.ts). The
// lists of the records agents draft show the agent badge from here.
export { default as AgentBadge } from './components/AgentBadge.vue'
export type { AgentDraftKind } from './types/agentTypes'
