import { createMasterDataStore } from '@/shared/stores/createMasterDataStore'
import { archiveSourceItemType } from '../api/archiveSourceItemType'
import { createSourceItemType } from '../api/createSourceItemType'
import { getSourceItemTypes } from '../api/getSourceItemTypes'
import { placeSourceItemType } from '../api/placeSourceItemType'
import { restoreSourceItemType } from '../api/restoreSourceItemType'
import { updateSourceItemType } from '../api/updateSourceItemType'

// items is the complete source item type list other features pick from.
export const useSourceItemTypesStore = createMasterDataStore('sourceItemTypes', {
  api: {
    list: getSourceItemTypes,
    create: createSourceItemType,
    update: updateSourceItemType,
    archive: archiveSourceItemType,
    restore: restoreSourceItemType,
    place: placeSourceItemType,
  },
  filters: {
    name: 'contains',
  },
})
