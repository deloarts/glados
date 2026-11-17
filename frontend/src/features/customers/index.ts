// Public barrel of the customers feature. Other code imports through here
// (enforced by eslint).

export { useCustomersStore } from './stores/customersStore'

export type { CustomerResponse } from './types/customerResponse'

export { default as CustomerSelect } from './components/CustomerSelect.vue'
export { useCustomerById } from './composables/useCustomerById'
