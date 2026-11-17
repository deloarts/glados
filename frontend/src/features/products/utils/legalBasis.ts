import { toDateKey, todayStart } from '@/core/utils/dates'

/**
 * The legal act for machinery a product is assessed against. Directive
 * 2006/42/EC applies to machinery placed on the market up to 2027-01-19,
 * Regulation (EU) 2023/1230 from 2027-01-20. Until then either may be
 * chosen, because machinery is already designed to the Regulation ahead of
 * the date.
 */
export type LegalBasis = 'directive' | 'regulation'
export const LEGAL_BASES: readonly LegalBasis[] = ['directive', 'regulation']

/** The first day on which Regulation (EU) 2023/1230 applies instead of Directive 2006/42/EC. */
export const REGULATION_APPLIES_FROM = '2027-01-20'

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

/** The planned date, or today when no date is planned, the earliest the machine could be placed on the market. */
function effectiveDate(placingOnMarket: string | null, today: Date): string {
  return placingOnMarket && ISO_DATE.test(placingOnMarket) ? placingOnMarket : toDateKey(today)
}

/** The legal act that applies to machinery placed on the market on the given date. */
export function legalBasisFor(
  placingOnMarket: string | null,
  today: Date = todayStart(),
): LegalBasis {
  return effectiveDate(placingOnMarket, today) >= REGULATION_APPLIES_FROM ? 'regulation' : 'directive'
}

/**
 * Whether the Directive is chosen for machinery placed on the market when
 * only the Regulation applies any more. The Regulation chosen ahead of the
 * date is not a conflict.
 */
export function legalBasisOutdated(
  basis: LegalBasis | null,
  placingOnMarket: string | null,
  today: Date = todayStart(),
): boolean {
  return basis === 'directive' && legalBasisFor(placingOnMarket, today) === 'regulation'
}
