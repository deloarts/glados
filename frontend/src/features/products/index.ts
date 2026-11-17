// Public barrel of the products feature. Other features import through here
// (enforced by eslint).

export { getProducts } from './api/getProducts'
export { getProductSummary } from './api/getProductSummary'
export { useProductsStore } from './stores/productsStore'
export { default as ProductContactsSection } from './components/ProductContactsSection.vue'
export { default as ProductFilesTab } from './components/ProductFilesTab.vue'
export { default as ProductFormDialog } from './components/ProductFormDialog.vue'
export { default as ProductPicture } from './components/ProductPicture.vue'
export { LEGAL_BASES, REGULATION_APPLIES_FROM, legalBasisFor, legalBasisOutdated } from './utils/legalBasis'

export type { LegalBasis } from './utils/legalBasis'
export type { ProductBaseResponse, ProductResponse } from './types/productResponse'
