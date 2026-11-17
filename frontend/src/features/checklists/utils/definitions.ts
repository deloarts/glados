import { HYDRAULICS } from './hydraulics'
import { PNEUMATICS } from './pneumatics'
import { ROBOTICS } from './robotics'
import { isChecklistType } from './types'
import type { ChecklistDefinition, ChecklistItem, ChecklistType, Translate } from './types'

export const CHECKLISTS: Readonly<Record<ChecklistType, ChecklistDefinition>> = {
  hydraulics: HYDRAULICS,
  pneumatics: PNEUMATICS,
  robotics: ROBOTICS,
}

/** Message keys under `checklists`; texts are keyed by the stable ids. */
const ROOT = 'checklists'

export function typeLabelKey(type: ChecklistType): string {
  return `${ROOT}.types.${type}`
}

/** The translated name of a stored type; an unknown one shows as stored. */
export function typeLabel(type: string, t: Translate): string {
  return isChecklistType(type) ? t(typeLabelKey(type)) : type
}

export function partTitleKey(type: ChecklistType, partKey: string): string {
  return `${ROOT}.${type}.parts.${partKey}`
}

export function sectionTitleKey(type: ChecklistType, sectionKey: string): string {
  return `${ROOT}.${type}.sections.${sectionKey}`
}

export function itemTextKey(type: ChecklistType, item: ChecklistItem): string {
  return `${ROOT}.${type}.items.${item.id}`
}

export function itemHintKey(type: ChecklistType, item: ChecklistItem): string {
  return `${ROOT}.${type}.hints.${item.id}`
}

/** `1.2/10.1`: section and position, the same in every language. */
export function itemPosition(definition: ChecklistDefinition, item: ChecklistItem): string {
  const section = definition.sectionByKey.get(item.sectionKey)
  return `${section?.number ?? '?'}/${item.number}`
}

/** The DOM id of an item row, so the summary can scroll to a finding. */
export function itemDomId(type: ChecklistType, item: ChecklistItem): string {
  return `checklist-${type}-${item.id.replace(/\./g, '-')}`
}

/** The icon a checklist type is shown with in lists. */
export const TYPE_ICONS: Readonly<Record<ChecklistType, string>> = {
  hydraulics: 'mdi-hydraulic-oil-level',
  pneumatics: 'mdi-air-filter',
  robotics: 'mdi-robot-industrial',
}
