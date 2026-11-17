import type { LegalBasis, Reference, Translate } from './types'

const ROOT = 'checklists'

/** The annex holding the essential health and safety requirements. */
export function machineryAnnex(basis: LegalBasis): string {
  return basis === 'regulation' ? 'III' : 'I'
}

/**
 * Renders a citation such as "ISO 4413:2010, 5.4.7.2.1" or, for the machinery
 * legal act, "Annex I 1.5.4" under the Directive and "Annex III 1.5.4" under
 * the Regulation.
 */
export function formatReference(ref: Reference, basis: LegalBasis, t: Translate): string {
  if (ref.kind === 'machinery') {
    return t(`${ROOT}.references.machinery`, { annex: machineryAnnex(basis), point: ref.point })
  }
  const doc = t(`${ROOT}.documents.${ref.doc}`)
  switch (ref.kind) {
    case 'clause':
      return ref.clause === undefined ? doc : `${doc}, ${ref.clause}`
    case 'intro':
      return `${doc}, ${t(`${ROOT}.references.introduction`)}`
    case 'table':
      return `${doc}, ${t(`${ROOT}.references.table`, { table: ref.table })}`
    case 'article':
      return `${doc}, ${t(`${ROOT}.references.article`, { article: ref.article })}`
    case 'annex':
      return ref.point === undefined
        ? `${doc}, ${t(`${ROOT}.references.annex`, { annex: ref.annex })}`
        : `${doc}, ${t(`${ROOT}.references.annexPoint`, { annex: ref.annex, point: ref.point })}`
  }
}

/**
 * Renders a list of citations, joining consecutive clauses of one document
 * ("ISO 4413:2010, 5.2, 5.4.1.6") and consecutive points of the machinery
 * legal act ("Annex I 1.7, 1.2.2") so a row of references stays short.
 */
export function formatReferences(refs: readonly Reference[], basis: LegalBasis, t: Translate): string[] {
  const out: string[] = []
  let previous: Reference | null = null
  for (const ref of refs) {
    const last = out.length - 1
    if (previous && last >= 0) {
      if (ref.kind === 'clause' && previous.kind === 'clause' && ref.doc === previous.doc && ref.clause && previous.clause) {
        out[last] = `${out[last]}, ${ref.clause}`
        previous = ref
        continue
      }
      if (ref.kind === 'machinery' && previous.kind === 'machinery') {
        out[last] = `${out[last]}, ${ref.point}`
        previous = ref
        continue
      }
    }
    out.push(formatReference(ref, basis, t))
    previous = ref
  }
  return out
}
