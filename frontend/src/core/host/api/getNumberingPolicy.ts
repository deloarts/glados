import { webApi } from '@/core/api/webRequest'

import type { Schemas } from '@/core/api/generated'

/**
 * How one item kind's part numbers are assigned. web_creation_allowed is
 * false only once PDM is enabled and the admin setting says so, and
 * external_pattern is a client-side hint ('' when unset) while the server
 * still decides on create and renumber.
 */
export type PartNumberPolicy = Schemas['PartNumberPolicy']

/** One row of the made-item revision field policy, the web column only. */
export type RevisionFieldPolicyEntry = Schemas['RevisionFieldPolicyEntry']

/** `ask` defers to a form-time choice; the rest are concrete MadeItemCatalogueStatus values. */
export type RevisionPolicy = Schemas['RevisionPolicy']

export type MadeItemPartNumberPolicy = Schemas['MadeItemPartNumberPolicy']

/**
 * The numbering policy of every item kind. The number patterns are
 * validation regexes for hand-entered numbers ('' means no enforcement), so
 * the forms reject a bad number before the round trip while the server
 * still enforces them. Item forms disable PDM and add-in owned inputs on a
 * CAD row only when pdm_enabled and cad_items_read_only are both true
 * (docs/FIELD_OWNERSHIP.md principle 3); this is presentation only.
 */
export type NumberingPolicy = Schemas['NumberingPolicy']

/**
 * How part numbers are assigned, so item forms can present the matching input
 * state. Readable by any authenticated user, unlike the full admin settings.
 */
export async function getNumberingPolicy(): Promise<NumberingPolicy> {
  return webApi.get('/host/numbering')
}
