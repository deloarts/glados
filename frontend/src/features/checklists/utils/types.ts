/**
 * The model behind the inspection checklists. A checklist type has parts
 * (documentation review, inspection of the built machine, instructions, or
 * the topic groups of the robotics list), parts have sections and sections
 * have items. Every item is answered with one of the answer states, may carry
 * a free remark, and is matched to its answer and its texts by a stable id.
 */

import type { LegalBasis } from '@/features/products'
import type { ChecklistOwner } from '../types/checklist'
import type { Translate } from '@/core/i18n'

type ChecklistOwnerKind = ChecklistOwner['kind']

export type { Translate }

export const CHECKLIST_TYPES = ['hydraulics', 'pneumatics', 'robotics'] as const
export type ChecklistType = (typeof CHECKLIST_TYPES)[number]

export function isChecklistType(value: string): value is ChecklistType {
  return (CHECKLIST_TYPES as readonly string[]).includes(value)
}

export const ANSWERS = ['na', 'yes', 'no', 'defect'] as const
export type Answer = (typeof ANSWERS)[number]

/** The answers that count as a finding, listed in the summary as problems. */
export const PROBLEM_ANSWERS: readonly Answer[] = ['no', 'defect']

/**
 * How a robotics requirement is verified, as listed in the verification table
 * of ISO 10218-2: A visual inspection, B practical test, C measurement,
 * D observation during operation, E review of application-specific
 * schematics, F review of safety-related software, G review of the
 * task-based risk assessment, H review of layout drawings and documents,
 * I review of specifications and information for use.
 */
export const VERIFICATION_METHODS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I'] as const
export type VerificationMethod = (typeof VERIFICATION_METHODS)[number]

/**
 * The legal act for machinery the checklist is assessed against, taken from
 * the product like the rest of the machine data.
 */
export type { LegalBasis } from '@/features/products'

/**
 * What a checklist of each type may belong to, the rule the backend keeps in
 * checklist_type.py. The machinery checklists assess one machine, so they
 * belong to the product that describes it.
 */
export const CHECKLIST_OWNER_KINDS: Readonly<Record<ChecklistType, readonly ChecklistOwnerKind[]>> = {
  hydraulics: ['product'],
  pneumatics: ['product'],
  robotics: ['product'],
}

/** Whether a checklist of some type can be started for this kind of owner. */
export function canStartChecklistFor(kind: ChecklistOwnerKind): boolean {
  return CHECKLIST_TYPES.some((type) => CHECKLIST_OWNER_KINDS[type].includes(kind))
}

/** Standards and other documents an item can cite, labelled through i18n. */
export const DOCUMENT_KEYS = [
  'iso4413',
  'iso4414',
  'iso12100',
  'iso13850',
  'iso1219_1',
  'iso1219_2',
  'iec81346_2',
  'iec60204_1',
  'ped',
  'spvd',
  'en14359',
  'en286_1',
  'en856',
  'iso13732_1',
  'ifaValves',
  'iso10218_1',
  'iso10218_2',
  'iso13849_1',
  'iec62061',
  'iso13854',
  'iso13855',
  'iso13857',
  'iso14119',
  'iso14120',
  'iso14122',
  'iso11161',
  'iec61496_1',
  'isoTs15066',
] as const
export type DocumentKey = (typeof DOCUMENT_KEYS)[number]

/**
 * A citation. `machinery` points into the essential health and safety
 * requirements of the machinery legal act, Annex I of the Directive or
 * Annex III of the Regulation, which keeps the numbering of the points cited
 * here; which annex is shown follows the checklist's legal basis.
 */
export type Reference =
  | { kind: 'clause'; doc: DocumentKey; clause?: string }
  | { kind: 'intro'; doc: DocumentKey }
  | { kind: 'table'; doc: DocumentKey; table: string }
  | { kind: 'article'; doc: DocumentKey; article: string }
  | { kind: 'annex'; doc: DocumentKey; annex: string; point?: string }
  | { kind: 'machinery'; point: string }

export interface ChecklistItem {
  /** `<section key>.<item key>`, unique within the checklist type. */
  id: string
  key: string
  sectionKey: string
  /** Position within the section, `3` for a main item and `3.1` for a sub-item. */
  number: string
  level: 0 | 1
  refs: readonly Reference[]
  methods: readonly VerificationMethod[]
  /** True when the item has an explanatory hint text next to its question. */
  hint: boolean
  /** Ids of related items in the same checklist, rendered as cross references. */
  see: readonly string[]
}

export interface ChecklistSection {
  key: string
  partKey: string
  /** `1.2` for the second section of part 1. */
  number: string
  items: readonly ChecklistItem[]
}

export interface ChecklistPart {
  key: string
  number: string
  sections: readonly ChecklistSection[]
}

export interface ChecklistDefinition {
  type: ChecklistType
  parts: readonly ChecklistPart[]
  sections: readonly ChecklistSection[]
  items: readonly ChecklistItem[]
  itemById: ReadonlyMap<string, ChecklistItem>
  sectionByKey: ReadonlyMap<string, ChecklistSection>
}

/**
 * The data at the top of a checklist. Dates are `YYYY-MM-DD` or empty. The
 * `owner*` fields and the machine data (designation through legal basis)
 * are copied from the owner, the machine data from its product, whenever a
 * draft is saved, so a released checklist keeps what they were at the time;
 * they are never typed in. Who checked the checklist is its release, not a
 * header field.
 */
export interface ChecklistHeader {
  ownerNumber: string
  ownerCustomer: string
  ownerProduct: string
  ownerManager: string
  designation: string
  machineType: string
  placingOnMarket: string
  installationSite: string
  installationLocation: string
  legalBasis: LegalBasis
  assessedBy: string
  assessedOn: string
  reason: string
  notes: string
}

export interface ChecklistState {
  header: ChecklistHeader
  /** Answer per item id; an item without an entry is unanswered. */
  answers: Record<string, Answer>
  /** Remark per item id; an item without an entry has no remark. */
  remarks: Record<string, string>
}
