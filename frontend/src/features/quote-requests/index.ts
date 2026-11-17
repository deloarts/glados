// Public barrel of the quote-requests feature. Other features import through
// here (enforced by eslint). Export only what other features consume: the
// Manage Quotes panel with its row model, and the "in quotation" markers.

export { useOpenQuoteRequestLinks } from './composables/useOpenQuoteRequestLinks'
export { mergeQuotePanelRows } from './utils/quotePanelRows'

export type { QuotePanelRow, QuotePanelShare } from './utils/quotePanelRows'
export type { OpenQuoteRequestRef } from './types/quoteRequestsResponse'

export { default as InQuotationTag } from './components/InQuotationTag.vue'
export { default as QuoteRequestPanel } from './components/QuoteRequestPanel.vue'
