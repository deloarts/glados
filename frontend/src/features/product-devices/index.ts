// Public barrel of the product-devices feature. Other features import
// through here (enforced by eslint). Export only what other features consume.

export { useProductDeviceResourcesStore } from './stores/productDeviceResourcesStore'
export { usePlcEnvironmentsStore } from './stores/plcEnvironmentsStore'
export { useProductDevicesViewStore } from './stores/productDevicesViewStore'
export { getProductDevices } from './api/productDevicesApi'
export { useDeviceRenderings } from './composables/useDeviceRenderings'

export type { ProductDevice } from './types/productDevice'

export { default as ProductDevicesTab } from './components/ProductDevicesTab.vue'
export { default as ProductDeviceDialog } from './components/ProductDeviceDialog.vue'
export { default as ProductDevicesControls } from './components/ProductDevicesControls.vue'
export { default as ProductDevicesViews } from './components/ProductDevicesViews.vue'
