import { computed } from 'vue'

import { createMasterDataStore } from '@/shared/stores/createMasterDataStore'
import { archiveInspectionMethod } from '../api/archiveInspectionMethod'
import { createInspectionMethod } from '../api/createInspectionMethod'
import { getInspectionMethods } from '../api/getInspectionMethods'
import { placeInspectionMethod } from '../api/placeInspectionMethod'
import { restoreInspectionMethod } from '../api/restoreInspectionMethod'
import { updateInspectionMethod } from '../api/updateInspectionMethod'

// items is the complete method list other features pick from.
export const useInspectionMethodsStore = createMasterDataStore('inspectionMethods', {
  api: {
    list: getInspectionMethods,
    create: createInspectionMethod,
    update: updateInspectionMethod,
    archive: archiveInspectionMethod,
    restore: restoreInspectionMethod,
    place: placeInspectionMethod,
  },
  filters: {
    name: 'contains',
  },
  extend: ({ items }) => ({
    // Excludes archived methods, so a new step or process defaults to a live
    // method while `items` stays complete for rendering existing references.
    activeItems: computed(() => items.value.filter((m) => !m.archived)),
  }),
})
