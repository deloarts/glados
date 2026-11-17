import { createMasterDataStore } from '@/shared/stores/createMasterDataStore'
import { archiveMachinePool } from '../api/archiveMachinePool'
import { createMachinePool } from '../api/createMachinePool'
import { getMachinePools } from '../api/getMachinePools'
import { placeMachinePool } from '../api/placeMachinePool'
import { restoreMachinePool } from '../api/restoreMachinePool'
import { updateMachinePool } from '../api/updateMachinePool'

// No other feature picks pools from this store, so items is the management
// table's current page. The filter keys match the backend query params, so
// the machines and creator columns set `filter-field` to these names rather
// than their display fields.
export const useMachinePoolsStore = createMasterDataStore('machinePools', {
  api: {
    list: getMachinePools,
    create: createMachinePool,
    update: updateMachinePool,
    archive: archiveMachinePool,
    restore: restoreMachinePool,
    place: placeMachinePool,
  },
  filters: {
    name: 'contains',
    machine_id: 'equals',
    creator_id: 'equals',
  },
  tableOnly: true,
  extend: ({ items, total }) => ({
    clear(): void {
      items.value = []
      total.value = 0
    },
  }),
})
