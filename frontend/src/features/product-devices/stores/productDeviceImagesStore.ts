import { createFilesStore } from '@/core/stores/createFilesStore'

import {
  getDeviceSlotFiles,
  removeDeviceSlotFile,
  uploadDeviceSlotFile,
  type DeviceImageCategory,
  type DeviceSlotFile,
} from '../api/deviceImagesApi'

/**
 * A device's two images in the shape the shared files section expects, keyed
 * by device id. Both slots hold one image each, so an upload replaces the
 * slot's previous file.
 */
export const useProductDeviceImagesStore = createFilesStore<DeviceSlotFile, DeviceImageCategory>(
  'productDeviceImages',
  {
    getForItem: getDeviceSlotFiles,
    upload: uploadDeviceSlotFile,
    remove: removeDeviceSlotFile,
    itemIdOf: (file) => file.device_id,
    singletonCategories: ['device_rendering', 'device_assembly'],
  },
)
