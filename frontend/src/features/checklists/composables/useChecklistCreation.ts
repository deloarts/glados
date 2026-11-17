import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { createChecklist } from '../api/createChecklist'
import type { ChecklistOwner, ChecklistResponse } from '../types/checklist'
import { CHECKLISTS } from '../utils/definitions'
import { CHECKLIST_DEFINITION_VERSION } from '../utils/index'
import { ownerIds } from '../utils/owner'
import { emptyHeader, headerToRecord } from '../utils/state'
import { checklistTitle } from '../utils/title'
import type { ChecklistType } from '../utils/types'
import { useOwnerData } from './useOwnerData'

/**
 * Starts an empty checklist of a type for an owner, with the owner's data
 * already in its header, and saves it right away so it has a page of its
 * own to be filled in on.
 */
export function useChecklistCreation() {
  const { t } = useI18n()
  const translate = (key: string, params?: Record<string, unknown>) => (params ? t(key, params) : t(key))
  const ownerData = useOwnerData()
  const creating = ref(false)

  async function create(type: ChecklistType, owner: ChecklistOwner): Promise<ChecklistResponse> {
    creating.value = true
    try {
      const header = { ...emptyHeader(), ...(await ownerData.load(owner)) }
      return await createChecklist({
        type,
        title: checklistTitle(type, header, translate),
        header: headerToRecord(header),
        answers: {},
        remarks: {},
        definition_version: CHECKLIST_DEFINITION_VERSION,
        item_count: CHECKLISTS[type].items.length,
        ...ownerIds(owner),
      })
    } finally {
      creating.value = false
    }
  }

  return { create, creating }
}
