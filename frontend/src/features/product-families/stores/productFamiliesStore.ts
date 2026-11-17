import { createMasterDataStore } from '@/shared/stores/createMasterDataStore'
import { archiveProductFamily } from '../api/archiveProductFamily'
import { createProductFamily } from '../api/createProductFamily'
import { getProductFamilies } from '../api/getProductFamilies'
import { placeProductFamily } from '../api/placeProductFamily'
import { restoreProductFamily } from '../api/restoreProductFamily'
import { updateProductFamily } from '../api/updateProductFamily'

// items is the complete product family list other features pick from.
export const useProductFamiliesStore = createMasterDataStore('productFamilies', {
  api: {
    list: getProductFamilies,
    create: createProductFamily,
    update: updateProductFamily,
    archive: archiveProductFamily,
    restore: restoreProductFamily,
    place: placeProductFamily,
  },
  filters: {
    name: 'contains',
  },
})
