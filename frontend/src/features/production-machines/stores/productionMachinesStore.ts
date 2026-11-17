import { createMasterDataStore, useToggleGroupBy } from '@/shared/stores/createMasterDataStore'
import { archiveProductionMachine } from '../api/archiveProductionMachine'
import { createProductionMachine } from '../api/createProductionMachine'
import { getProductionMachines } from '../api/getProductionMachines'
import { placeProductionMachine } from '../api/placeProductionMachine'
import { restoreProductionMachine } from '../api/restoreProductionMachine'
import { updateProductionMachine } from '../api/updateProductionMachine'

export type ProductionMachineGroupBy = 'capability' | null

// No other feature picks machines from this store, so items is the
// management table's current page. The filter keys match the backend query
// params, so the capability and creator columns set `filter-field` to these
// names rather than their display fields.
export const useProductionMachinesStore = createMasterDataStore('productionMachines', {
  api: {
    list: getProductionMachines,
    create: createProductionMachine,
    update: updateProductionMachine,
    archive: archiveProductionMachine,
    restore: restoreProductionMachine,
    place: placeProductionMachine,
  },
  filters: {
    internal_name: 'contains',
    vendor: 'contains',
    model: 'contains',
    fabrication_method_id: 'equals',
    creator_id: 'equals',
  },
  tableOnly: true,
  extend: ({ items, total }) => ({
    ...useToggleGroupBy<Exclude<ProductionMachineGroupBy, null>>(),
    clear(): void {
      items.value = []
      total.value = 0
    },
  }),
})
