// The Data Portal hits of the create dialog search. A hit whose order code 1
// is exactly the text searched for, character for character, is a 100 %
// match; the portal ranks its hits fuzzily, so those are moved to the top.
import type { EdpSearchHit } from '../types/boughtItemsEdpTypes'

export function isExactOrderCodeMatch(hit: EdpSearchHit, query: string): boolean {
  const code = hit.draft.order_code_1
  return !!code && code === query.trim()
}

export function exactMatchesFirst(hits: EdpSearchHit[], query: string): EdpSearchHit[] {
  const exact = hits.filter((hit) => isExactOrderCodeMatch(hit, query))
  return [...exact, ...hits.filter((hit) => !exact.includes(hit))]
}
