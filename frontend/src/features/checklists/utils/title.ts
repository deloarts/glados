import { typeLabelKey } from './definitions'
import type { ChecklistHeader, ChecklistType, Translate } from './types'

const MAX_TITLE_LENGTH = 200

/**
 * The title a checklist is saved under, named after its owner and the
 * machine designation: "Hydraulics checklist, P-1001, Press 12".
 */
export function checklistTitle(type: ChecklistType, header: Readonly<ChecklistHeader>, t: Translate): string {
  const typeLabel = t(typeLabelKey(type))
  const subject = [header.ownerNumber.trim(), header.designation.trim()].filter((part) => part !== '').join(', ')
  const text = subject
    ? t('checklists.savedTitle', { type: typeLabel, subject })
    : t('checklists.savedTitlePlain', { type: typeLabel })
  return text.slice(0, MAX_TITLE_LENGTH)
}
