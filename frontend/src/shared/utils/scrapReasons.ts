import type { Schemas } from '@/core/api/generated'

export type ScrapReason = Schemas['ScrapReason']

// Mirrors the backend's ScrapReason value object (scrap_reason.py). One
// frontend constant every scrap/rejection reason picker reads its options
// from, so a later addition (e.g. a concession outcome) needs no duplicate
// edit across dialogs. It lives in shared because production and the order
// delivery dialogs both record scrap.
export const SCRAP_REASONS: ScrapReason[] = [
  'operator_error',
  'tool_breakage',
  'machine_fault',
  'material_defect',
  'program_error',
  'out_of_tolerance',
  'supplier_damage',
  'transport_damage',
  'wrong_spec',
  'other',
]

export function scrapReasonLabelKey(reason: ScrapReason): string {
  return `production.scrap.reasons.${reason}`
}
