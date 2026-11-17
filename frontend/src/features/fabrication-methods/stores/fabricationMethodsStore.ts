import { computed } from 'vue'

import { createMasterDataStore } from '@/shared/stores/createMasterDataStore'
import { archiveFabricationMethod } from '../api/archiveFabricationMethod'
import { createFabricationMethod } from '../api/createFabricationMethod'
import { getFabricationMethods } from '../api/getFabricationMethods'
import { placeFabricationMethod } from '../api/placeFabricationMethod'
import { restoreFabricationMethod } from '../api/restoreFabricationMethod'
import { updateFabricationMethod } from '../api/updateFabricationMethod'

// items is the complete method list other features pick from.
export const useFabricationMethodsStore = createMasterDataStore('fabricationMethods', {
  api: {
    list: getFabricationMethods,
    create: createFabricationMethod,
    update: updateFabricationMethod,
    archive: archiveFabricationMethod,
    restore: restoreFabricationMethod,
    place: placeFabricationMethod,
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
