import type { Schemas } from '@/core/api/generated'

// The EPLAN Data Portal on single bought items.
export type EdpPartSummary = Schemas['EdpPartSummaryResponse']
export type EdpItemDraft = Schemas['EdpItemDraftResponse']
export type EdpSearchHit = Schemas['EdpSearchHitResponse']
export type EdpItemLookup = Schemas['EdpItemLookupResponse']
export type EdpLookupFieldRow = Schemas['EdpLookupFieldResponse']
export type EdpLookupField = EdpLookupFieldRow['field']
