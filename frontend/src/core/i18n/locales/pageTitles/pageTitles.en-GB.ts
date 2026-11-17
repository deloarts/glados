// Fallback h1 and document-title text for a route whose page title depends on an
// entity that has not loaded yet, merged into the en-GB locale. Each detail view
// replaces it with the loaded entity's own name or number once it arrives, see
// usePageTitle's setPageTitle.
export default {
  projectDetail: 'Project',
  productDetail: 'Product',
  boughtItemDetail: 'Bought Item',
  madeItemDetail: 'Made Item',
  sourceItemDetail: 'Source Item',
  orderDetail: 'Order',
  quoteRequestDetail: 'Quote Request',
  lotDetail: 'Lot',
  productionOrderDetail: 'Production Order',
}
