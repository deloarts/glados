import type { Schemas } from '@/core/api/generated'

type ExtraCostKind = Schemas['ExtraCostKind']

/**
 * Every kind of extra cost in the order a picker lists them. Orders and the
 * offers of a quote request share the kinds, so an awarded offer's costs
 * carry over unchanged.
 */
export const EXTRA_COST_KINDS = [
  'shipping',
  'packaging',
  'small_order_surcharge',
  'material_surcharge',
  'setup',
  'certificate',
  'express_surcharge',
  'customs',
  'discount',
  'other',
] as const satisfies readonly ExtraCostKind[]

/** One extra cost as an editor holds it; the amount is in cents. */
export interface ExtraCostDraft {
  kind: ExtraCostKind
  amount: number | null
  label: string
  note: string
  lineId: number | null
}

/** A discount is stored as a positive amount and subtracted. */
export function signedExtraCost(kind: ExtraCostKind, amount: number): number {
  return kind === 'discount' ? -amount : amount
}

/** A kind that says too little on its own needs a label. */
export function extraCostNeedsLabel(kind: ExtraCostKind): boolean {
  return kind === 'other'
}

/** The text a cost shows: its label, else the kind's name. */
export function extraCostName(
  t: (key: string) => string,
  cost: { kind: ExtraCostKind; label: string | null },
): string {
  return cost.label || t(`common.extraCosts.kinds.${cost.kind}`)
}

/** The first problem of a draft list as an i18n key, or null when it can be saved. */
export function extraCostDraftError(drafts: ExtraCostDraft[]): string | null {
  for (const draft of drafts) {
    if (draft.amount === null || draft.amount <= 0) return 'common.extraCosts.errors.amount'
    if (extraCostNeedsLabel(draft.kind) && !draft.label.trim()) return 'common.extraCosts.errors.label'
  }
  return null
}
