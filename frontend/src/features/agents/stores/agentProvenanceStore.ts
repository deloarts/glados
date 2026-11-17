import { defineStore } from 'pinia'
import { reactive } from 'vue'

import { findAgentCreatedRecords } from '../api/agentsApi'
import type { AgentCreatedRecord } from '../types/agentTypes'

// The backend takes at most this many references per lookup.
const BATCH_LIMIT = 200
// A record not created by an agent is asked about again after this long,
// since a live list shows an agent's draft before its call is logged.
const MISS_TTL_MS = 30_000

interface Entry {
  record: AgentCreatedRecord | null
  at: number
}

/**
 * Which records an AI agent created, for the agent badge in the lists. Every
 * badge asks for its own record, and the asks of one render are sent as one
 * lookup, so a list page costs one request however many rows it shows. An
 * agent's record stays known; a miss is asked again after a short while.
 * Who created a record is the same for every user, so nothing here needs
 * clearing at logout.
 */
export const useAgentProvenanceStore = defineStore('agentProvenance', () => {
  const entries = reactive(new Map<string, Entry>())
  const queued = new Set<string>()
  let flushing: Promise<void> | null = null

  function isFresh(ref: string): boolean {
    const entry = entries.get(ref)
    if (!entry) return false
    return entry.record !== null || Date.now() - entry.at < MISS_TTL_MS
  }

  async function flush(): Promise<void> {
    // Let the rest of the render queue its records first.
    await Promise.resolve()
    const refs = [...queued]
    queued.clear()
    flushing = null
    for (let start = 0; start < refs.length; start += BATCH_LIMIT) {
      const batch = refs.slice(start, start + BATCH_LIMIT)
      try {
        const found = new Map((await findAgentCreatedRecords(batch)).map((r) => [r.ref, r]))
        const now = Date.now()
        for (const ref of batch) entries.set(ref, { record: found.get(ref) ?? null, at: now })
      } catch {
        // No badge is shown for a lookup that failed; the next render asks again.
      }
    }
  }

  /** Queues a lookup of `ref` unless a fresh answer is known. */
  function request(ref: string): void {
    if (isFresh(ref) || queued.has(ref)) return
    queued.add(ref)
    flushing ??= flush()
  }

  function recordOf(ref: string): AgentCreatedRecord | null {
    return entries.get(ref)?.record ?? null
  }

  return { request, recordOf }
})
