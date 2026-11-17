// Fallback h1 and document-title text for a route whose page title depends on an
// entity that has not loaded yet, merged into the de-AT locale. Each detail view
// replaces it with the loaded entity's own name or number once it arrives, see
// usePageTitle's setPageTitle.
export default {
  projectDetail: 'Projekt',
  productDetail: 'Produkt',
  boughtItemDetail: 'Zukaufteil',
  madeItemDetail: 'Fertigungsteil',
  sourceItemDetail: 'Rohblock',
  orderDetail: 'Bestellung',
  quoteRequestDetail: 'Angebotsanfrage',
  lotDetail: 'Los',
  productionOrderDetail: 'Fertigungsauftrag',
}
